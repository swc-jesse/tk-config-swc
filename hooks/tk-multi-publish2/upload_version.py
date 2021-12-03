# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import sgtk
import os
import datetime
import re

HookBaseClass = sgtk.get_hook_baseclass()

class UploadVersionPlugin(HookBaseClass):
    @property
    def icon(self):
        """
        Path to an png icon on disk
        """

        # look for icon one level up from this hook's folder in "icons" folder
        return os.path.join(self.disk_location, os.curdir, "icons", "review.png")

    @property
    def name(self):
        """
        One line display name describing the plugin
        """
        return "Upload for review"

    @property
    def description(self):
        """
        Verbose, multi-line description of what the plugin does. This can
        contain simple html for formatting.
        """
        publisher = self.parent

        shotgun_url = publisher.sgtk.shotgun_url

        media_page_url = "%s/page/media_center" % (shotgun_url,)
        mobile_url = "https://help.autodesk.com/view/SGSUB/ENU/?guid=SG_Supervisor_Artist_sa_mobile_review_html"
        rv_url = "https://help.autodesk.com/view/SGSUB/ENU/?guid=SG_RV_rv_manuals_rv_easy_setup_html"

        return """
        Upload the file to ShotGrid for review.<br><br>

        A <b>Version</b> entry will be created in ShotGrid and a transcoded
        copy of the file will be attached to it. The file can then be reviewed
        via the project's <a href='%s'>Media</a> page, <a href='%s'>RV</a>, or
        the <a href='%s'>ShotGrid Review</a> mobile app.
        """ % (
            media_page_url,
            rv_url,
            mobile_url,
        )

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
        The type string should be one of the data types that toolkit accepts as
        part of its environment configuration.
        """
        return {
            "File Extensions": {
                "type": "str",
                "default": "jpeg, jpg, png, mov, mp4, pdf, avi",
                "description": "File Extensions of files to include",
            },
            "Upload": {
                "type": "bool",
                "default": True,
                "description": "Upload content to ShotGrid?",
            },
            "Link Local File": {
                "type": "bool",
                "default": True,
                "description": "Should the local file be referenced by ShotGrid",
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

        # we use "video" since that's the mimetype category.
        return ["file.image", "file.video", "playblast.*"]

    def accept(self, settings, item):
        p4_data = item.properties.get("p4_data")
        if p4_data: 
            if p4_data["action"] == "delete":
                return {"accepted": False}
                        
        # get the base settings
        settings = super(UploadVersionPlugin, self).accept(settings, item)
        if(item.type_spec.split(".")[0] != "playblast"):
            # set the default checked state
            settings["checked"] = False
        return settings

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
        publish_name = item.properties.get("publish_name")
        if not publish_name:
            version_path = self.get_next_version_name(item,item.properties["path"])
            version_path_components = self.publisher.util.get_file_path_components(version_path)
            publish_name = version_path_components["filename"]  
            
            self.logger.debug("Using prior version info to determine publish version.")

            self.logger.debug("Publish name: %s" % (publish_name,))  
            item.properties["publish_name"] = publish_name          
        super(UploadVersionPlugin, self).validate(settings, item)

    def finalize(self, settings, item):
        """
        Execute the finalization pass. This pass executes once all the publish
        tasks have completed, and can for example be used to version up files.
        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """

        # Increment version number based on how many versions
        self.publisher = self.parent
        path = item.properties["path"]
        version = item.properties["sg_version_data"]

        type_class = item.type_spec.split(".")[0] 

        if(type_class == "playblast"):
            os.remove(path)
            self.logger.info(
                "Playblast deleted after uploading for file: %s" % (path,),
                extra={
                    "action_show_in_shotgun": {
                        "label": "Show Version",
                        "tooltip": "Reveal the version in ShotGrid.",
                        "entity": version,
                    }
                },
            )        
        else:
            super(UploadVersionPlugin, self).finalize(settings, item)

    def get_next_version_name(self, item, path):
        # Increment version number based on how many versions
        self.publisher = self.parent
        path = item.properties["path"]

        # use the path's filename as the base publish name
        path_components = self.publisher.util.get_file_path_components(path)
        publish_name = path_components["filename"]

        # See how many prior versions there are
        filters = [
            ['entity', 'is', self._get_version_entity(item)]
        ]

        prior_versions = self.publisher.shotgun.find("Version",filters,['code'])      

        regex = r"(" + re.escape(publish_name.split('.')[0]) + r"){1}(\.v\d)?\.\w*$"

        x = [i for i in prior_versions if re.match(regex,i['code'])]   

        # Set the publish name of this item as the next version
        version_number = len(x)+1     
        version_path = self.publisher.util.get_version_path(path,version_number)

        return version_path      
