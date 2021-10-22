# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import glob
import os
import maya.cmds as cmds
import maya.mel as mel
import sgtk

HookBaseClass = sgtk.get_hook_baseclass()

class MayaSessionCollector(HookBaseClass):
    """
    Collector that operates on the maya session. Should inherit from the basic
    collector hook.
    """

    @property
    def settings(self):
        """
        Dictionary defining the settings that this collector expects to receive
        through the settings parameter in the process_current_session and
        process_file methods.

        A dictionary on the following form::

            {
                "Settings Name": {
                    "type": "settings_type",
                    "default": "default_value",
                    "description": "One line description of the setting"
            }

        The type string should be one of the data types that toolkit accepts as
        part of its environment configuration.
        """

        # grab any base class settings
        collector_settings = super(MayaSessionCollector, self).settings or {}

        # settings specific to this collector
        maya_session_settings = {
            "Work Template": {
                "type": "template",
                "default": None,
                "description": "Template path for artist work files. Should "
                "correspond to a template defined in "
                "templates.yml. If configured, is made available"
                "to publish plugins via the collected item's "
                "properties. ",
            },
        }

        # update the base settings with these settings
        collector_settings.update(maya_session_settings)

        return collector_settings

    def process_current_session(self, settings, parent_item):
        """
        Analyzes the current session open in Maya and parents a subtree of
        items under the parent_item passed in.

        :param dict settings: Configured settings for this collector
        :param parent_item: Root item instance

        """

        # create an item representing the current maya session
        item = self.collect_current_maya_session(settings, parent_item)
        project_root = item.properties["project_root"]

        # if we can determine a project root, collect other files to publish
        if project_root:     
            self.logger.info(
                "Current Maya project is: %s." % (project_root,),
                extra={
                    "action_button": {
                        "label": "Change Project",
                        "tooltip": "Change to a different Maya project",
                        "callback": lambda: mel.eval('setProject ""'),
                    }
                },
            )
            self.collect_fbx_animations(settings, item, project_root)
        else:
            self.logger.info(
                "Could not determine the current Maya project.",
                extra={
                    "action_button": {
                        "label": "Set Project",
                        "tooltip": "Set the Maya project",
                        "callback": lambda: mel.eval('setProject ""'),
                    }
                },
            )

    def collect_current_maya_session(self, settings, parent_item):
        """
        Creates an item that represents the current maya session.

        :param parent_item: Parent Item instance

        :returns: Item of type maya.session
        """

        publisher = self.parent

        # get the path to the current file
        path = cmds.file(query=True, sn=True)
        path = sgtk.util.ShotgunPath.normalize(path)
        # determine the display name for the item
        if path:
            file_info = publisher.util.get_file_path_components(path)
            display_name = file_info["filename"]
            session_info = {
                "item_type":"maya.session",
                "type_display":"Maya Session",
                "display_name":file_info["filename"]
                }         
            session_item = super(MayaSessionCollector, self).process_file(settings, parent_item, path, custom_info=session_info)

            # discover the project root which helps in discovery of other
            # publishable items
            project_root = cmds.workspace(q=True, rootDirectory=True)
            session_item.properties["project_root"] = project_root

            # if a work template is defined, add it to the item properties so
            # that it can be used by attached publish plugins
            work_template_setting = settings.get("Work Template")
            if work_template_setting:

                work_template = publisher.engine.get_template_by_name(
                    work_template_setting.value
                )

                # store the template on the item for use by publish plugins. we
                # can't evaluate the fields here because there's no guarantee the
                # current session path won't change once the item has been created.
                # the attached publish plugins will need to resolve the fields at
                # execution time.
                session_item.properties["work_template"] = work_template
                self.logger.debug("Work template defined for Maya collection.")

            self.logger.info("Collected current Maya scene")

            return session_item

    def collect_fbx_animations(self, settings, parent_item, project_root):     
        """
        Looks for exported FBX files that match this file name

        :param parent_item: Parent Item instance
        :param str project_root: The maya project root to search for FBX files        
        """           
        # ensure the alembic cache dir exists
        fbx_file = os.path.join(project_root, parent_item.name.split(".")[0] + ".fbx")
        if not os.path.exists(fbx_file):
            return

        self.logger.info(
            "Processing found FBX file: %s" % (fbx_file,),
            extra={"action_show_folder": {"path": os.path.dirname(fbx_file)}},
        )

        item_info = self._collect_item_info(parent_item, fbx_file)
        if item_info["item_type"] != "file.motionbuilder":
            return

        # allow the base class to collect and create the item. it knows how
        # to handle alembic files
        super(MayaSessionCollector, self).process_file(settings, parent_item, fbx_file)                  