# Copyright (c) 2017 ShotGrid Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the ShotGrid Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the ShotGrid Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by ShotGrid Software Inc.

import os
import pprint
import traceback

import sgtk
# from sgtk.util.filesystem import copy_file, ensure_folder_exists

HookBaseClass = sgtk.get_hook_baseclass()

class PublishPlugin(HookBaseClass):
    """
    """

    @property
    def icon(self):
        """
        Path to an png icon on disk
        """

        # look for icon one level up from this hook's folder in "icons" folder
        return os.path.join(self.disk_location, os.pardir, os.pardir, "icons", "perforce.png")

    @property
    def name(self):
        """
        One line display name describing the plugin
        """
        return "Publish to Perforce & ShotGrid"

    @property
    def description(self):
        """
        Verbose, multi-line description of what the plugin does. This can
        contain simple html for formatting.
        """
        return """
        Checks the file into to Perforce and creates the <b>Published File</b>
        entry in ShotGrid which will include a reference to the file's current
        path on disk.
        """

    @property
    def settings(self):
        """
        Dictionary defining the settings that this plugin expects to recieve
        through the settings parameter in the accept, validate, publish and
        finalize methods.

        A dictionary on the following form::

            {
                "Settings Name": {
                    "type": "settings_type",
                    "default": "default_value",
                    "description": "One line description of the setting"
            }

        The type string should be one of the data types that toolkit accepts
        as part of its environment configuration.
        """
        return {
            "File Types": {
                "type": "list",
                "default": [
                    ["Alias File", "wire"],
                    ["Alembic Cache", "abc"],
                    ["3dsmax Scene", "max"],
                    ["NukeStudio Project", "hrox"],
                    ["Houdini Scene", "hip", "hipnc"],
                    ["Maya Scene", "ma", "mb"],
                    ["Motion Builder FBX", "fbx"],
                    ["Nuke Script", "nk"],
                    ["Photoshop Image", "psd", "psb"],
                    ["VRED Scene", "vpb", "vpe", "osb"],
                    ["Rendered Image", "dpx", "exr"],
                    ["Texture", "tiff", "tx", "tga", "dds"],
                    ["Image", "jpeg", "jpg", "png"],
                    ["Movie", "mov", "mp4"],
                    ["PDF", "pdf"],
                ],
                "description": (
                    "List of file types to include. Each entry in the list "
                    "is a list in which the first entry is the ShotGrid "
                    "published file type and subsequent entries are file "
                    "extensions that should be associated."
                ),
            },
        }

    @property
    def item_filters(self):
        """
        List of item types that this plugin is interested in.

        Only items matching entries in this list will be presented to the
        accept() method. Strings can contain glob patters such as *, for example
        ["maya.*", "file.maya"]
        """
        return ["file.*"]

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

        path = item.properties.path

        # log the accepted file and display a button to reveal it in the fs
        self.logger.info(
            "Perforce publish plugin accepted: {}".format(path),
            extra={"action_show_folder": {"path": path}},
        )

        # return the accepted info
        type = item.type_spec
        if(type == "file.playblast"):
            return {"accepted": False}
        return {"accepted": True}            

    def validate(self, settings, item):
        """
        Validates the given item to check that it is ok to publish.

        Returns a boolean to indicate validity.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process

        :returns: True if item is valid, False otherwise.
        """

        publisher = self.parent
        path = item.properties.get("path")
        target_context = self._find_task_context(path)

        # ---- determine the information required to validate
        if not item.context.entity and not target_context.entity:
            self.logger.error("This file is not under a known Asset folder:")
            self.logger.error("  %s" % (path,))      
            return False      
        elif target_context.entity != item.context.entity:
            self.logger.error("This file is not under the correct Asset folder:")
            self.logger.error("  %s" % (path,))
            self.logger.error("Should be under %s not %s" % (target_context.entity,item.context.entity))
            return False
        elif target_context.task != item.context.task:
            if not item.local_properties.get("ignore_bad_stuff", False):
                self.logger.warning("This file looks to be under the following Task folder:")
                self.logger.warning("  %s" % (target_context.task,))
                self.logger.warning("Consider updating the Task accordingly.", extra={
                    "action_button":{
                    "label": "Ignore",
                    "tooltip": "Ignore this warning",
                    "callback": self._ignore_warning,
                    "args": {"item": item}
                    },
                })
                raise Exception("Potential bad path!")

        extension = path.split(".")[-1]
        if extension.lower() != extension:
            self.logger.error("This file extension is not lowercase:")
            self.logger.error("  %s, should be %s" % (path,extension.lower()))      
            return False                

        # We allow the information to be pre-populated by the collector or a
        # base class plugin. They may have more information than is available
        # here such as custom type or template settings.

        publish_path = self.get_publish_path(settings, item)
        publish_name = self.get_publish_name(settings, item)

        self.logger.info("A Publish will be created in ShotGrid and linked to:")
        self.logger.info("  %s" % (path,))

        return True

    def _ignore_warning(self, item):
        item.local_properties["ignore_bad_stuff"] = True
        print("ignoring", item)

    def publish(self, settings, item):
        """
        Executes the publish logic for the given item and settings.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """

        publisher = self.parent

        # ---- determine the information required to publish

        # We allow the information to be pre-populated by the collector or a
        # base class plugin. They may have more information than is available
        # here such as custom type or template settings.

        publish_type = self.get_publish_type(settings, item)
        publish_name = self.get_publish_name(settings, item)
        publish_version = self.get_publish_version(settings, item)
        publish_path = self.get_publish_path(settings, item)
        publish_dependencies_paths = self.get_publish_dependencies(settings, item)
        publish_user = self.get_publish_user(settings, item)
        publish_fields = self.get_publish_fields(settings, item)
        # catch-all for any extra kwargs that should be passed to register_publish.
        publish_kwargs = self.get_publish_kwargs(settings, item)

        # if the parent item has publish data, get it id to include it in the list of
        # dependencies
        publish_dependencies_ids = []
        if "sg_publish_data" in item.parent.properties:
            publish_dependencies_ids.append(
                item.parent.properties.sg_publish_data["id"]
            )

        # handle copying of work to publish if templates are in play
        # self._copy_work_to_publish(settings, item)

        # arguments for publish registration
        self.logger.info("Collecting publish data...")
        publish_data = {
            "tk": publisher.sgtk,
            "context": item.context,
            "comment": item.description,
            "path": publish_path,
            "name": publish_name,
            "created_by": publish_user,
            "version_number": publish_version,
            "thumbnail_path": item.get_thumbnail_as_path(),
            "published_file_type": publish_type,
            "dependency_paths": publish_dependencies_paths,
            "dependency_ids": publish_dependencies_ids,
            "sg_fields": publish_fields,
        }

        # add extra kwargs
        publish_data.update(publish_kwargs)

        # store the publish data for the post_phase hook to pick up
        self.logger.info(
            "Storing Publish data...",
            extra={
                "action_show_more_info": {
                    "label": "Publish Data",
                    "tooltip": "Show the complete Publish data dictionary",
                    "text": "<pre>%s</pre>" % (pprint.pformat(publish_data),),
                }
            },
        )

        item.properties.publish_data = publish_data

    def finalize(self, settings, item):
        """
        Execute the finalization pass. This pass executes once
        all the publish tasks have completed, and can for example
        be used to version up files.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """

        publisher = self.parent

        # get the data for the publish that was just created in SG
        publish_data = item.properties.get('sg_publish_data')

        if publish_data:
            # ensure conflicting publishes have their status cleared
            publisher.util.clear_status_for_conflicting_publishes(
                item.context, publish_data
            )

            self.logger.info("Cleared the status of all previous, conflicting publishes")

            path = item.properties.path
            self.logger.info(
                "Publish created for file: %s" % (path,),
                extra={
                    "action_show_in_shotgun": {
                        "label": "Show Publish",
                        "tooltip": "Open the Publish in ShotGrid.",
                        "entity": publish_data,
                    }
                },
            )

    def get_publish_template(self, settings, item):
        """
        Get a publish template for the supplied settings and item.

        :param settings: This plugin instance's configured settings
        :param item: The item to determine the publish template for

        :return: A template representing the publish path of the item or
            None if no template could be identified.
        """

        return item.get_property("publish_template")

    def get_publish_type(self, settings, item):
        """
        Get a publish type for the supplied settings and item.

        :param settings: This plugin instance's configured settings
        :param item: The item to determine the publish type for

        :return: A publish type or None if one could not be found.
        """

        # publish type explicitly set or defined on the item
        publish_type = item.get_property("publish_type")
        if publish_type:
            return publish_type

        # fall back to the path info hook logic
        publisher = self.parent
        path = item.properties.path

        # get the publish path components
        path_info = publisher.util.get_file_path_components(path)

        # determine the publish type
        extension = path_info["extension"]

        # ensure lowercase and no dot
        if extension:
            extension = extension.lstrip(".").lower()

            for type_def in settings["File Types"].value:

                publish_type = type_def[0]
                file_extensions = type_def[1:]

                if extension in file_extensions:
                    # found a matching type in settings. use it!
                    return publish_type

        # --- no pre-defined publish type found...

        if extension:
            # publish type is based on extension
            publish_type = "%s File" % extension.capitalize()
        else:
            # no extension, assume it is a folder
            publish_type = "Folder"

        return publish_type

    def get_publish_path(self, settings, item):
        """
        Get a publish path for the supplied settings and item.

        :param settings: This plugin instance's configured settings
        :param item: The item to determine the publish path for

        :return: A string representing the output path to supply when
            registering a publish for the supplied item

        Extracts the publish path via the configured work and publish templates
        if possible.
        """

        # publish type explicitly set or defined on the item
        publish_path = item.get_property("publish_path")
        if publish_path:
            return publish_path

        # fall back to template/path logic
        path = item.properties.path

        work_template = item.properties.get("work_template")
        publish_template = self.get_publish_template(settings, item)

        work_fields = []
        publish_path = None

        # We need both work and publish template to be defined for template
        # support to be enabled.
        if work_template and publish_template:
            if work_template.validate(path):
                work_fields = work_template.get_fields(path)

            missing_keys = publish_template.missing_keys(work_fields)

            if missing_keys:
                self.logger.warning(
                    "Not enough keys to apply work fields (%s) to "
                    "publish template (%s)" % (work_fields, publish_template)
                )
            else:
                publish_path = publish_template.apply_fields(work_fields)
                self.logger.debug(
                    "Used publish template to determine the publish path: %s"
                    % (publish_path,)
                )
        else:
            self.logger.debug("publish_template: %s" % publish_template)
            self.logger.debug("work_template: %s" % work_template)

        if not publish_path:
            publish_path = path
            self.logger.debug(
                "Could not validate a publish template. Publishing in place."
            )

        return publish_path

    def get_publish_version(self, settings, item):
        """
        Get the publish version for the supplied settings and item.

        :param settings: This plugin instance's configured settings
        :param item: The item to determine the publish version for

        Extracts the publish version via the configured work template if
        possible. Will fall back to using the path info hook.
        """

        # publish version explicitly set or defined on the item
        publish_version = item.get_property("publish_version")
        if publish_version:
            return publish_version

        # fall back to the template/path_info logic
        publisher = self.parent
        path = item.properties.path

        work_template = item.properties.get("work_template")
        work_fields = None
        publish_version = None

        if work_template:
            if work_template.validate(path):
                self.logger.debug("Work file template configured and matches file.")
                work_fields = work_template.get_fields(path)

        if work_fields:
            # if version number is one of the fields, use it to populate the
            # publish information
            if "version" in work_fields:
                publish_version = work_fields.get("version")
                self.logger.debug("Retrieved version number via work file template.")

        else:
            self.logger.debug("Using path info hook to determine publish version.")
            publish_version = publisher.util.get_version_number(path)
            if publish_version is None:
                publish_version = 1

        return publish_version

    def get_publish_name(self, settings, item):
        """
        Get the publish name for the supplied settings and item.

        :param settings: This plugin instance's configured settings
        :param item: The item to determine the publish name for

        Uses the path info hook to retrieve the publish name.
        """

        # publish name explicitly set or defined on the item
        publish_name = item.get_property("publish_name")
        if publish_name:
            return publish_name

        # fall back to the path_info logic
        publisher = self.parent
        path = item.properties.path

        if "sequence_paths" in item.properties:
            # generate the name from one of the actual files in the sequence
            name_path = item.properties.sequence_paths[0]
            is_sequence = True
        else:
            name_path = path
            is_sequence = False

        return publisher.util.get_publish_name(name_path, sequence=is_sequence)

    def get_publish_dependencies(self, settings, item):
        """
        Get publish dependencies for the supplied settings and item.

        :param settings: This plugin instance's configured settings
        :param item: The item to determine the publish template for

        :return: A list of file paths representing the dependencies to store in
            SG for this publish
        """

        # local properties first
        dependencies = item.local_properties.get("publish_dependencies")

        # have to check against `None` here since `[]` is valid and may have
        # been explicitly set on the item
        if dependencies is None:
            # get from the global item properties.
            dependencies = item.properties.get("publish_dependencies")

        if dependencies is None:
            # not set globally or locally on the item. make it []
            dependencies = []

        return dependencies

    def get_publish_user(self, settings, item):
        """
        Get the user that will be associated with this publish.

        If publish_user is not defined as a ``property`` or ``local_property``,
        this method will return ``None``.

        :param settings: This plugin instance's configured settings
        :param item: The item to determine the publish template for

        :return: A user entity dictionary or ``None`` if not defined.
        """
        return item.get_property("publish_user", default_value=None)

    def get_publish_fields(self, settings, item):
        """
        Get additional fields that should be used for the publish. This
        dictionary is passed on to :meth:`tank.util.register_publish` as the
        ``sg_fields`` keyword argument.

        If publish_fields is not defined as a ``property`` or
        ``local_property``, this method will return an empty dictionary.

        :param settings: This plugin instance's configured settings
        :param item: The item to determine the publish template for

        :return: A dictionary of field names and values for those fields.
        """
        return item.get_property("publish_fields", default_value={})

    def get_publish_kwargs(self, settings, item):
        """
        Get kwargs that should be passed to :meth:`tank.util.register_publish`.
        These kwargs will be used to update the kwarg dictionary that is passed
        when calling :meth:`tank.util.register_publish`, meaning that any value
        set here will supersede a value already retrieved from another
        ``property`` or ``local_property``.

        If publish_kwargs is not defined as a ``property`` or
        ``local_property``, this method will return an empty dictionary.

        :param settings: This plugin instance's configured settings
        :param item: The item to determine the publish template for

        :return: A dictionary of kwargs to be passed to
                 :meth:`tank.util.register_publish`.
        """
        return item.get_property("publish_kwargs", default_value={})

    def _find_task_context(self, path):
        # Try to get the context more specifically from the path on disk
        tk = sgtk.sgtk_from_path( path )
        context = tk.context_from_path(path)

        # In case the task folder is not registered for some reason, we can try to find it
        if not context.task:
            if context.step:
                if context.step["name"] == "Animations":
                    file_name = os.path.splitext(os.path.basename(path))[0]
                    # SWC JR: This could get slow if there are a lot of tasks, not sure if there is a way to query instead            
                    tasks = context.sgtk.shotgun.find("Task", [["entity", "is", context.entity],["step", "is", context.step]], ['content'])
                    for task in tasks:
                        if task['content'] in file_name:
                            # We found the task
                            context = tk.context_from_entity("Task", task['id'])
                else:
                    file_folder = os.path.basename(os.path.dirname(path))
                    context_task = context.sgtk.shotgun.find_one("Task", [["content", "is", file_folder],["entity", "is", context.entity],["step", "is", context.step]])
                    if context_task:
                        context = tk.context_from_entity("Task", context_task["id"])
        return context

    ############################################################################
    # protected methods

    # def _copy_work_to_publish(self, settings, item):
    #     """
    #     This method handles copying work file path(s) to a designated publish
    #     location.
    #
    #     This method requires a "work_template" and a "publish_template" be set
    #     on the supplied item.
    #
    #     The method will handle copying the "path" property to the corresponding
    #     publish location assuming the path corresponds to the "work_template"
    #     and the fields extracted from the "work_template" are sufficient to
    #     satisfy the "publish_template".
    #
    #     The method will not attempt to copy files if any of the above
    #     requirements are not met. If the requirements are met, the file will
    #     ensure the publish path folder exists and then copy the file to that
    #     location.
    #
    #     If the item has "sequence_paths" set, it will attempt to copy all paths
    #     assuming they meet the required criteria with respect to the templates.
    #
    #     """
    #
    #     # ---- ensure templates are available
    #     work_template = item.properties.get("work_template")
    #     if not work_template:
    #         self.logger.debug(
    #             "No work template set on the item. "
    #             "Skipping copy file to publish location."
    #         )
    #         return
    #
    #     publish_template = self.get_publish_template(settings, item)
    #     if not publish_template:
    #         self.logger.debug(
    #             "No publish template set on the item. "
    #             "Skipping copying file to publish location."
    #         )
    #         return
    #
    #     # ---- get a list of files to be copied
    #
    #     # by default, the path that was collected for publishing
    #     work_files = [item.properties.path]
    #
    #     # if this is a sequence, get the attached files
    #     if "sequence_paths" in item.properties:
    #         work_files = item.properties.get("sequence_paths", [])
    #         if not work_files:
    #             self.logger.warning(
    #                 "Sequence publish without a list of files. Publishing "
    #                 "the sequence path in place: %s" % (item.properties.path,)
    #             )
    #             return
    #
    #     # ---- copy the work files to the publish location
    #
    #     for work_file in work_files:
    #
    #         if not work_template.validate(work_file):
    #             self.logger.warning(
    #                 "Work file '%s' did not match work template '%s'. "
    #                 "Publishing in place." % (work_file, work_template)
    #             )
    #             return
    #
    #         work_fields = work_template.get_fields(work_file)
    #
    #         missing_keys = publish_template.missing_keys(work_fields)
    #
    #         if missing_keys:
    #             self.logger.warning(
    #                 "Work file '%s' missing keys required for the publish "
    #                 "template: %s" % (work_file, missing_keys)
    #             )
    #             return
    #
    #         publish_file = publish_template.apply_fields(work_fields)
    #
    #         # copy the file
    #         try:
    #             publish_folder = os.path.dirname(publish_file)
    #             ensure_folder_exists(publish_folder)
    #             copy_file(work_file, publish_file)
    #         except Exception:
    #             raise Exception(
    #                 "Failed to copy work file from '%s' to '%s'.\n%s"
    #                 % (work_file, publish_file, traceback.format_exc())
    #             )
    #
    #         self.logger.debug(
    #             "Copied work file '%s' to publish file '%s'."
    #             % (work_file, publish_file)
    #         )

    # def _get_next_version_info(self, path, item):
    #     """
    #     Return the next version of the supplied path.
    #
    #     If templates are configured, use template logic. Otherwise, fall back to
    #     the zero configuration, path_info hook logic.
    #
    #     :param str path: A path with a version number.
    #     :param item: The current item being published
    #
    #     :return: A tuple of the form::
    #
    #         # the first item is the supplied path with the version bumped by 1
    #         # the second item is the new version number
    #         (next_version_path, version)
    #     """
    #
    #     if not path:
    #         self.logger.debug("Path is None. Can not determine version info.")
    #         return None, None
    #
    #     publisher = self.parent
    #
    #     # if the item has a known work file template, see if the path
    #     # matches. if not, warn the user and provide a way to save the file to
    #     # a different path
    #     work_template = item.properties.get("work_template")
    #     work_fields = None
    #
    #     if work_template:
    #         if work_template.validate(path):
    #             work_fields = work_template.get_fields(path)
    #
    #     # if we have template and fields, use them to determine the version info
    #     if work_fields and "version" in work_fields:
    #
    #         # template matched. bump version number and re-apply to the template
    #         work_fields["version"] += 1
    #         next_version_path = work_template.apply_fields(work_fields)
    #         version = work_fields["version"]
    #
    #     # fall back to the "zero config" logic
    #     else:
    #         next_version_path = publisher.util.get_next_version_path(path)
    #         cur_version = publisher.util.get_version_number(path)
    #         if cur_version is not None:
    #             version = cur_version + 1
    #         else:
    #             version = None
    #
    #     return next_version_path, version

    # def _save_to_next_version(self, path, item, save_callback):
    #     """
    #     Save the supplied path to the next version on disk.
    #
    #     :param path: The current path with a version number
    #     :param item: The current item being published
    #     :param save_callback: A callback to use to save the file
    #
    #     Relies on the _get_next_version_info() method to retrieve the next
    #     available version on disk. If a version can not be detected in the path,
    #     the method does nothing.
    #
    #     If the next version path already exists, logs a warning and does
    #     nothing.
    #
    #     This method is typically used by subclasses that bump the current
    #     working/session file after publishing.
    #     """
    #
    #     (next_version_path, version) = self._get_next_version_info(path, item)
    #
    #     if version is None:
    #         self.logger.debug(
    #             "No version number detected in the publish path. "
    #             "Skipping the bump file version step."
    #         )
    #         return None
    #
    #     self.logger.info("Incrementing file version number...")
    #
    #     # nothing to do if the next version path can't be determined or if it
    #     # already exists.
    #     if not next_version_path:
    #         self.logger.warning("Could not determine the next version path.")
    #         return None
    #     elif os.path.exists(next_version_path):
    #         self.logger.warning(
    #             "The next version of the path already exists",
    #             extra={"action_show_folder": {"path": next_version_path}},
    #         )
    #         return None
    #
    #     # save the file to the new path
    #     save_callback(next_version_path)
    #     self.logger.info("File saved as: %s" % (next_version_path,))
    #
    #     return next_version_path
