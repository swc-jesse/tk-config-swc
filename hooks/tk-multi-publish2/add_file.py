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
import sgtk

HookBaseClass = sgtk.get_hook_baseclass()

class AddPublishPlugin(HookBaseClass):
    """
    """
    @property
    def icon(self):
        """
        Path to an png icon on disk
        """

        # look for icon one level up from this hook's folder in "icons" folder
        return os.path.join(self.disk_location, "icons", "p4_file_add.png")

    @property
    def name(self):
        """
        One line display name describing the plugin
        """
        return "ADD to Perforce & ShotGrid"

    @property
    def description(self):
        """
        Verbose, multi-line description of what the plugin does. This can
        contain simple html for formatting.
        """
        return """
        Adds the file to Perforce and creates the <b>Published File</b>
        entry in ShotGrid which will include a reference to the file's current
        path on disk.
        """
        
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
        p4_data = item.properties.get("p4_data")
        if p4_data: 
            if p4_data["action"] == "add":
                # log the accepted file and display a button to reveal it in the fs
                # self.logger.info(
                #     "Perforce ADD plugin accepted: {}".format(path),
                #     extra={"action_show_folder": {"path": path}},
                # )

                # return the accepted info
                return super(AddPublishPlugin, self).accept(settings, item)
        
        return {"accepted": False}          
