import os
import pprint
import traceback

import sgtk
from sgtk.util.filesystem import copy_file, ensure_folder_exists

HookBaseClass = sgtk.get_hook_baseclass()
TK_FRAMEWORK_PERFORCE_NAME = "tk-framework-perforce_v0.x.x"


class MayaPerforceFileCheckin(HookBaseClass):
    """
    Plugin for checking any file into Perforce.

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
        return "Check-in to Perforce"

    @property
    def description(self):
        """
        Verbose, multi-line description of what the plugin does. This can
        contain simple html for formatting.
        """

        return """
        Checks the file into to Perforce.
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
        return {}

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
            "Perforce check-in plugin accepted: %s" % (path,),
            extra={"action_show_folder": {"path": path}},
        )

        # return the accepted info
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

        self.p4_fw = self.load_framework(TK_FRAMEWORK_PERFORCE_NAME)
        self.logger.debug("Perforce framework loaded.")

        # test to ensure the file can be edited
        p4 = self.p4_fw.connection.connect()
        self.p4_fw.util.open_file_for_edit(p4, path, test_only=True)

        self.logger.info("A revision will be checked in to Perforce for:")
        self.logger.info("  %s" % (path,))

        return True

    def publish(self, settings, item):
        """
        Executes the publish logic for the given item and settings.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """

        publisher = self.parent
        path = item.properties.get("path")

        # open a Perforce connection:
        self.logger.info("Connecting to Perforce...")
        p4 = self.p4_fw.connection.connect()

        # Ensure the file is checked out/added to depot:
        self.logger.info("Ensuring file is checked out...")
        self.p4_fw.util.open_file_for_edit(p4, path, add_if_new=True)

        # create a new changelist for all files being published:
        self.logger.info("Creating new Perforce changelist...")
        new_change = self.p4_fw.util.create_change(p4, item.description or "Shotgun publish")

        # and add the file to this change:
        self.logger.info("Adding the file to the change...")
        self.p4_fw.util.add_to_change(p4, new_change, path)

        # submit the change:
        self.logger.info("Submitting the change...")
        self.p4_fw.util.submit_change(p4, new_change)

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
