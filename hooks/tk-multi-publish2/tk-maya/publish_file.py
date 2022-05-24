# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import maya.cmds as cmds
import maya.mel as mel
import sgtk
from sgtk.util.filesystem import ensure_folder_exists
from tank_vendor import six

HookBaseClass = sgtk.get_hook_baseclass()


class MayaSessionPublishPlugin(HookBaseClass):
    """
    Plugin for publishing an open maya session.

    This hook relies on functionality found in the base file publisher hook in
    the publish2 app and should inherit from it in the configuration. The hook
    setting for this plugin should look something like this::

        hook: "{self}/publish_file.py:{engine}/tk-multi-publish2/basic/publish_session.py"

    """

    # NOTE: The plugin icon and name are defined by the base file plugin.

    @property
    def description(self):
        """
        Verbose, multi-line description of what the plugin does. This can
        contain simple html for formatting.
        """

        return super(MayaSessionPublishPlugin, self).description

    @property
    def settings(self):
        """
        Dictionary defining the settings that this plugin expects to receive
        through the settings parameter in the accept, validate, publish and
        finalize methods.

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

        # inherit the settings from the base publish plugin
        base_settings = super(MayaSessionPublishPlugin, self).settings or {}

        # settings specific to this class
        maya_publish_settings = {
            "Publish Template": {
                "type": "template",
                "default": None,
                "description": "Template path for published work files. Should"
                "correspond to a template defined in "
                "templates.yml.",
            }
        }

        # update the base settings
        base_settings.update(maya_publish_settings)

        return base_settings

    @property
    def item_filters(self):
        """
        List of item types that this plugin is interested in.

        Only items matching entries in this list will be presented to the
        accept() method. Strings can contain glob patters such as *, for example
        ["maya.*", "file.maya"]
        """
        return ["maya.session", "file.*"]

    def accept(self, settings, item):
        """
        Method called by the publisher to determine if an item is of any
        interest to this plugin. Only items matching the filters defined via the
        item_filters property will be presented to this method.

        A publish task will be generated for each item accepted here. Returns a
        dictionary with the following booleans:

            - accepted: Indicates if the plugin is interested in this value at
                all. Required.
            - enabled: If True, the plugin will be enabled in the UI, otherwise
                it will be disabled. Optional, True by default.
            - visible: If True, the plugin will be visible in the UI, otherwise
                it will be hidden. Optional, True by default.
            - checked: If True, the plugin will be checked in the UI, otherwise
                it will be unchecked. Optional, True by default.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process

        :returns: dictionary with boolean keys accepted, required and enabled
        """

        # if a publish template is configured, disable context change. This
        # is a temporary measure until the publisher handles context switching
        # natively.

        if(item.type.split(".")[0] != "playblast"):
            if(item.type == "maya.session"):
                if settings.get("Publish Template").value:
                    item.context_change_allowed = False

                path = _session_path()

                if not path:
                    # the session has not been saved before (no path determined).
                    # provide a save button. the session will need to be saved before
                    # validation will succeed.
                    self.logger.warn(
                        "The Maya session has not been saved.", extra=_get_save_as_action()
                    )

                self.logger.info(
                    "Maya '%s' plugin accepted the current Maya session." % (self.name,)
                )
            else:
                self.logger.info(
                    "Maya '%s' plugin accepted file." % (self.name,)
                )            
            return {"accepted": True, "checked": True}
        else:
            return {"accepted": False}

    def validate(self, settings, item):
        """
        Validates the given item to check that it is ok to publish. Returns a
        boolean to indicate validity.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        :returns: True if item is valid, False otherwise.
        """

        publisher = self.parent
        path = _session_path()

        # ---- ensure the session has been saved
        if(item.type == "maya.session"):
            if not path:
                # the session still requires saving. provide a save button.
                # validation fails.
                error_msg = "The Maya session has not been saved."
                self.logger.error(error_msg, extra=_get_save_as_action())
                raise Exception(error_msg)

            # ensure we have an updated project root
            project_root = cmds.workspace(q=True, rootDirectory=True)
            item.properties["project_root"] = project_root

            # log if no project root could be determined.
            if not project_root:
                self.logger.info(
                    "Your session is not part of a maya project.",
                    extra={
                        "action_button": {
                            "label": "Set Project",
                            "tooltip": "Set the maya project",
                            "callback": lambda: mel.eval('setProject ""'),
                        }
                    },
                )

            # ---- check the session against any attached work template

            # get the path in a normalized state. no trailing separator,
            # separators are appropriate for current os, no double separators,
            # etc.
            path = sgtk.util.ShotgunPath.normalize(path)

            # if the session item has a known work template, see if the path
            # matches. if not, warn the user and provide a way to save the file to
            # a different path
            work_template = item.properties.get("work_template")
            if work_template:
                if not work_template.validate(path):
                    self.logger.warning(
                        "The current session does not match the configured work "
                        "file template.",
                        extra={
                            "action_button": {
                                "label": "Save File",
                                "tooltip": "Save the current Maya session to a "
                                "different file name",
                                # will launch wf2 if configured
                                "callback": _get_save_as_action(),
                            }
                        },
                    )
                else:
                    self.logger.debug("Work template configured and matches session file.")
            else:
                self.logger.debug("No work template configured.")

            # ---- populate the necessary properties and call base class validation

            # populate the publish template on the item if found
            publish_template_setting = settings.get("Publish Template")
            publish_template = publisher.engine.get_template_by_name(
                publish_template_setting.value
            )
            if publish_template:
                item.properties["publish_template"] = publish_template

            # set the session path on the item for use by the base plugin validation
            # step. NOTE: this path could change prior to the publish phase.
            item.properties["path"] = path

        # run the base class validation
        return super(MayaSessionPublishPlugin, self).validate(settings, item)

    def publish(self, settings, item):
        """
        Executes the publish logic for the given item and settings.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """

        # get the path in a normalized state. no trailing separator, separators
        # are appropriate for current os, no double separators, etc.
        path = sgtk.util.ShotgunPath.normalize(_session_path())

        if(item.type == "maya.session"):
            # ensure the session is saved
            _save_session(path)

            # update the item with the saved session path
            item.properties["path"] = path

            # add dependencies for the base class to register when publishing
            item.properties[
                "publish_dependencies"
            ] = _maya_find_additional_session_dependencies()

        # let the base class register the publish
        super(MayaSessionPublishPlugin, self).publish(settings, item)

    def finalize(self, settings, item):
        """
        Execute the finalization pass. This pass executes once all the publish
        tasks have completed, and can for example be used to version up files.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """

        # do the base class finalization
        super(MayaSessionPublishPlugin, self).finalize(settings, item)


def _maya_find_additional_session_dependencies():
    """
    Find additional dependencies from the session
    """

    # default implementation looks for references and
    # textures (file nodes) and returns any paths that
    # match a template defined in the configuration
    ref_paths = set()

    # first let's look at maya references
    ref_nodes = cmds.ls(references=True)
    for ref_node in ref_nodes:
        # get the path:

        # swc - ethanm - handling like maya does it in their scripts.
        try:
            ref_path = cmds.referenceQuery(ref_node, filename=True)
        except:
            cmds.warning('_maya_find_additional_session_dependencies: Ref Node "{}" has no filename.'.format(ref_node))
            continue

        # make it platform dependent
        # (maya uses C:/style/paths)
        ref_path = ref_path.replace("/", os.path.sep)
        if ref_path:
            ref_paths.add(ref_path)

    # now look at file texture nodes
    for file_node in cmds.ls(l=True, type="file"):
        # ensure this is actually part of this session and not referenced
        if cmds.referenceQuery(file_node, isNodeReferenced=True):
            # this is embedded in another reference, so don't include it in
            # the breakdown
            continue

        # get path and make it platform dependent
        # (maya uses C:/style/paths)
        texture_path = cmds.getAttr("%s.fileTextureName" % file_node).replace(
            "/", os.path.sep
        )
        if texture_path:
            ref_paths.add(texture_path)

    return list(ref_paths)


def _session_path():
    """
    Return the path to the current session
    :return:
    """
    path = cmds.file(query=True, sn=True)

    if path is not None:
        path = six.ensure_str(path)

    return path


def _save_session(path):
    """
    Save the current session to the supplied path.
    """

    # Maya can choose the wrong file type so we should set it here
    # explicitly based on the extension
    maya_file_type = None
    if path.lower().endswith(".ma"):
        maya_file_type = "mayaAscii"
    elif path.lower().endswith(".mb"):
        maya_file_type = "mayaBinary"

    # Maya won't ensure that the folder is created when saving, so we must make sure it exists
    folder = os.path.dirname(path)
    ensure_folder_exists(folder)

    cmds.file(rename=path)

    # save the scene:
    if maya_file_type:
        cmds.file(save=True, force=True, type=maya_file_type)
    else:
        cmds.file(save=True, force=True)


# TODO: method duplicated in all the maya hooks
def _get_save_as_action():
    """
    Simple helper for returning a log action dict for saving the session
    """

    engine = sgtk.platform.current_engine()

    # default save callback
    callback = cmds.SaveScene

    # if workfiles2 is configured, use that for file save
    if "tk-multi-workfiles2" in engine.apps:
        app = engine.apps["tk-multi-workfiles2"]
        if hasattr(app, "show_file_save_dlg"):
            callback = app.show_file_save_dlg

    return {
        "action_button": {
            "label": "Save As...",
            "tooltip": "Save the current session",
            "callback": callback,
        }
    }
