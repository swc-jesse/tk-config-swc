# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import mimetypes
import os
import sgtk
from tank_vendor import six
import re

HookBaseClass = sgtk.get_hook_baseclass()
TK_FRAMEWORK_PERFORCE_NAME = "tk-framework-perforce_v0.x.x"
TK_FRAMEWORK_SWC_NAME = "tk-framework-swc_v0.x.x"

# import ptvsd

# # Allow other computers to attach to ptvsd at this IP address and port.
# ptvsd.enable_attach(address=('localhost', 5678), redirect_output=True)

class BasicSceneCollector(HookBaseClass):
    """
    A basic collector that handles files and general objects.

    This collector hook is used to collect individual files that are browsed or
    dragged and dropped into the Publish2 UI. It can also be subclassed by other
    collectors responsible for creating items for a file to be published such as
    the current Maya session file.

    This plugin centralizes the logic for collecting a file, including
    determining how to display the file for publishing (based on the file
    extension).

    In addition to creating an item to publish, this hook will set the following
    properties on the item::

        path - The path to the file to publish. This could be a path
            representing a sequence of files (including a frame specifier).

        sequence_paths - If the item represents a collection of files, the
            plugin will populate this property with a list of files matching
            "path".

    """

    @property
    def common_file_info(self):
        """
        A dictionary of file type info that allows the basic collector to
        identify common production file types and associate them with a display
        name, item type, and config icon.

        The dictionary returned is of the form::

            {
                <Publish Type>: {
                    "extensions": [<ext>, <ext>, ...],
                    "icon": <icon path>,
                    "item_type": <item type>
                },
                <Publish Type>: {
                    "extensions": [<ext>, <ext>, ...],
                    "icon": <icon path>,
                    "item_type": <item type>
                },
                ...
            }

        See the collector source to see the default values returned.

        Subclasses can override this property, get the default values via
        ``super``, then update the dictionary as necessary by
        adding/removing/modifying values.
        """

        if not hasattr(self, "_common_file_info"):

            # do this once to avoid unnecessary processing
            self._common_file_info = {
                "Alembic Cache": {
                    "extensions": ["abc"],
                    "icon": self._get_icon_path("alembic.png"),
                    "item_type": "file.alembic",
                    "item_priority": 0,
                },
                "3dsmax Scene": {
                    "extensions": ["max"],
                    "icon": self._get_icon_path("3dsmax.png"),
                    "item_type": "file.3dsmax",
                    "item_priority": 10,
                },
                "Houdini Scene": {
                    "extensions": ["hip", "hipnc"],
                    "icon": self._get_icon_path("houdini.png"),
                    "item_type": "file.houdini",
                    "item_priority": 10,
                },
                "Maya Scene": {
                    "extensions": ["ma", "mb"],
                    "icon": self._get_icon_path("maya.png"),
                    "item_type": "file.maya",
                    "item_priority": 10,
                },
                "Motion Builder FBX": {
                    "extensions": ["fbx"],
                    "icon": self._get_icon_path("geometry.png"),
                    "item_type": "file.motionbuilder",
                    "item_priority": 3,
                },
                "Photoshop Image": {
                    "extensions": ["psd", "psb"],
                    "icon": self._get_icon_path("photoshop.png"),
                    "item_type": "file.photoshop",
                    "item_priority": 5,
                },
                "Texture Image": {
                    "extensions": ["tif", "tiff", "tx", "tga", "dds", "rat", "exr", "hdr"],
                    "icon": self._get_icon_path("texture.png"),
                    "item_type": "file.texture",
                    "item_priority": 0,
                },
                "PDF": {
                    "extensions": ["pdf"],
                    "icon": self._get_icon_path("file.png"),
                    "item_type": "file.image",
                    "item_priority": 0,                    
                },
                "Image": {
                    "extensions": ["png", "jpg", "gif"],
                    "icon": self._get_icon_path("file.png"),
                    "item_type": "file.image",
                    "item_priority": 0,                    
                },                
                "SpeedTree Modeler": {
                    "extensions": ["spm"],
                    "icon": self._get_icon_path("speedtree.png"),
                    "item_type": "file.speedtree",
                    "item_priority": 10,                    
                }, 
                "SpeedTree Export": {
                    "extensions": ["st9", "st"],
                    "icon": self._get_icon_path("speedtree.png"),
                    "item_type": "file.speedtree",
                    "item_priority": 5,                    
                },
                "Settings File": {
                    "extensions": ["pkl", "json"],
                    "icon": self._get_icon_path("file.png"),
                    "item_type": "file.settings",
                    "item_priority": 3,                    
                },
                "Mel Scripts": {
                    "extensions": ["mel"],
                    "icon": self._get_icon_path("file.png"),
                    "item_type": "script.maya",
                    "item_priority": 0,
                },      
                "Python Scripts": {
                    "extensions": ["py", "pyc"],
                    "icon": self._get_icon_path("file.png"),
                    "item_type": "script.python",
                    "item_priority": 0,
                },         
                "Movie": {
                    "extensions": ["mov", "avi", "mp4", "mpeg", "h264"],
                    "icon": self._get_icon_path("video.png"),
                    "item_type": "file.video",
                    "item_priority": 0,
                },      
                "Substance Designer": {
                    "extensions": ["sbs"],
                    "icon": self._get_icon_path("substance_designer.png"),
                    "item_type": "file.substance",
                    "item_priority": 7,
                },         
                "Substance Painter": {
                    "extensions": ["spp"],
                    "icon": self._get_icon_path("substance_painter.png"),
                    "item_type": "file.substance",
                    "item_priority": 9,
                },      
                "Zbrush Tool": {
                    "extensions": ["ztl"],
                    "icon": self._get_icon_path("zbrush.png"),
                    "item_type": "file.zbrush",
                    "item_priority": 5,
                },                                                                             
            }

        return self._common_file_info

    @property
    def common_folder_info(self):
        """
        A dictionary of file type info that allows the basic collector to
        identify common production file types and associate them with a display
        name, item type, and config icon.

        The dictionary returned is of the form::

            {
                <Publish Type>: {
                    "extensions": [<ext>, <ext>, ...],
                    "icon": <icon path>,
                    "item_type": <item type>
                },
                <Publish Type>: {
                    "extensions": [<ext>, <ext>, ...],
                    "icon": <icon path>,
                    "item_type": <item type>
                },
                ...
            }

        See the collector source to see the default values returned.

        Subclasses can override this property, get the default values via
        ``super``, then update the dictionary as necessary by
        adding/removing/modifying values.
        """

        if not hasattr(self, "_common_folder_info"):

            # do this once to avoid unnecessary processing
            self._common_folder_info = {
                "Snapshots": {
                    "name": "snapshots",
                    "item_type": "folder.snapshots",
                    "ignored": True,
                },      
                "Playblasts": {
                    "name": "playblasts",
                    "item_type": "folder.playblasts",
                    "ignored": False,
                },                               
                "Houdini Backups": {
                    "name": "backups",
                    "item_type": "folder.houdini.backups",
                    "ignored": True,
                },                                                                        
            }

        return self._common_folder_info

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
        return {}

    def process_current_session(self, settings, parent_item):
        """
        Analyzes the current scene open in a DCC and parents a subtree of items
        under the parent_item passed in.

        :param dict settings: Configured settings for this collector
        :param parent_item: Root item instance
        """

        # default implementation does not do anything
        pass

    def process_file(self, settings, parent_item, path, custom_info=None):
        """
        Analyzes the given file and creates one or more items
        to represent it.

        :param dict settings: Configured settings for this collector
        :param parent_item: Root item instance
        :param path: Path to analyze

        :returns: The main item that was created, or None if no item was created
            for the supplied path
        """    

        # make sure the path is normalized. no trailing separator, separators
        # are appropriate for the current os, no double separators, etc.
        path = sgtk.util.ShotgunPath.normalize(path)

        # Make the p4 connection
        self.p4_fw = self.load_framework(TK_FRAMEWORK_PERFORCE_NAME)
        self.logger.debug("Perforce framework loaded.")    

        # handle files and folders differently
        if os.path.isdir(path):
            folder = self.p4_fw.util.recursive_reconcile(path)                
            self._collect_folder(parent_item, folder)
            return None
        else:
            folder = self.p4_fw.util.recursive_reconcile(os.path.dirname(path))
            for items in folder.add_info, folder.edit_info, folder.delete_info, folder.open_info:
                for item in items:
                    if item["clientFile"] == path:
                        item_info = self._collect_item_info(parent_item,item["clientFile"],extra={"p4_data":item})
                        if custom_info:
                            item_info.update(custom_info)
                        collectedFile = self._collect_file(parent_item, item_info)
                        if not collectedFile:
                            return None

                        playblasts = os.path.join(os.path.dirname(path),"playblasts")
                        if(os.path.exists(playblasts)):
                            folder.recursive_scan(playblasts)
                            self._collect_folder(parent_item, folder)
                        return collectedFile
            self.logger.warn("File not added or changed in Perforce: %s" % (path,))
            return None

    def _collect_file(self, parent_item, item_info, frame_sequence=False):
        """
        Process the supplied file path.

        :param parent_item: parent item instance
        :param path: Path to analyze
        :param frame_sequence: Treat the path as a part of a sequence
        :returns: The item that was created
        """

        if item_info["item_type"].startswith("script"):
            return None
        # make sure the path is normalized. no trailing separator, separators
        # are appropriate for the current os, no double separators, etc.
        path = item_info["item_path"]

        if not self._ensure_unique(path, parent_item):
            return None

        publisher = self.parent

        # get info for the extension
        if os.path.basename(os.path.dirname(item_info["item_path"])) == "playblasts" and item_info["item_type"]:
            item_type = "playblast.%s" % item_info["item_type"].split(".")[1]
        else:
            item_type = item_info["item_type"]
        type_display = item_info["type_display"]
        extension = item_info["extension"]
        item_priority = item_info["item_priority"]
        p4_data = item_info["p4_data"]
        evaluated_path = path
        is_sequence = False

        if frame_sequence:
            # replace the frame number with frame spec
            seq_path = publisher.util.get_frame_sequence_path(path)
            if seq_path:
                evaluated_path = seq_path
                type_display = "%s Sequence" % (type_display,)
                item_type = "%s.%s" % (item_type, "sequence")
                is_sequence = True

        display_name = publisher.util.get_publish_name(path, sequence=is_sequence)

        # Try to get the context more specifically from the path on disk
        try:
            context = self.swc_fw.find_task_context(path)
        except(AttributeError):
            self.swc_fw = self.load_framework(TK_FRAMEWORK_SWC_NAME)
            context = self.swc_fw.find_task_context(path)

        # create and populate the item
        file_item = parent_item.create_item(item_type, type_display, display_name)
        file_item.set_icon_from_path(item_info["icon_path"])
        file_item.context_change_allowed = True

        # If we found a better context, set it here
        if context:
            file_item.context = context

        # if the supplied path is an image, use the path as the thumbnail.
        if item_type.endswith(".image") or item_type.endswith("file.texture"):
            file_item.set_thumbnail_from_path(path)
            file_item.set_icon_from_path(path)

            # disable thumbnail creation since we get it for free
            file_item.thumbnail_enabled = False
            file_item.thumbnail_explicit = True
        # if the supplied path is a SpeedTree SPM file, extract the thumbnail.
        elif item_type.startswith("file.speedtree") and extension.startswith("spm"):
            swc = self.load_framework("tk-framework-swc_v0.x.x")
            spm_utils = swc.import_module("SPM_Utils")
            temp_path = os.path.expandvars(r'%APPDATA%\Shotgun\Temp')
            os.makedirs(temp_path, exist_ok=True)
            out_path = os.path.join(temp_path,file_item.name.split(".")[0] + ".jpg")
            if spm_utils.SPMWriteThumbnail(path,out_path):
                file_item.set_thumbnail_from_path(out_path)
                file_item.set_icon_from_path(out_path)

                # disable thumbnail creation since we get it for free
                file_item.thumbnail_enabled = False
                file_item.thumbnail_explicit = True

        # all we know about the file is its path. set the path in its
        # properties for the plugins to use for processing.
        file_item.properties["path"] = evaluated_path
        file_item.properties["item_priority"] = item_priority
        file_item.properties["p4_data"] = p4_data

        if is_sequence:
            # include an indicator that this is an image sequence and the known
            # file that belongs to this sequence
            file_item.properties["sequence_paths"] = [path]

        self.logger.info("Collected file: %s" % (evaluated_path,))

        for child in item_info['children']:
            if os.path.basename(os.path.dirname(child["item_path"])) == "playblasts":
                child_item = self._collect_playblast(file_item, child)
            else:
                child_item = self._collect_file(file_item, child)
            # If items are children they should be forced under the parent task
            child_item.context_change_allowed = True
            child_item.context = context
            child_item_type = child["item_type"]
            child_item_ext = child["extension"]
            if child_item_type.startswith("file.speedtree") and child_item_ext.startswith("st") and extension.startswith("spm"):
                child_item.set_thumbnail_from_path(file_item.get_thumbnail_as_path())
                child_item.thumbnail_enabled = False
                child_item.thumbnail_explicit = True

        return file_item

    def _collect_folder(self, parent_item, folder):
        """
        Process the supplied folder path.

        :param parent_item: parent item instance
        :param folder: Reconciled Perforce data to analyze
        :returns: The items that were created
        """

        if not folder:
            return None

        item_infos = []
        file_items = []

        # Only process items that are added, edited or deleted in Perforce
        for items in folder.add_info, folder.edit_info, folder.delete_info, folder.open_info:
            for item in items:
                item_path = item["clientFile"]
                skip = False

                for key, value in self.common_folder_info.items():
                    if value["ignored"] and (value["name"] in os.path.dirname(item_path)):
                        skip = True

                if not skip:        
                    item_infos.append(self._collect_item_info(parent_item,item_path,extra={"p4_data":item}))
        
        item_infos = self._process_hierarchy(list(item_infos),parent_item)

        for item_info in item_infos:
            # Process each file we find
            if os.path.basename(os.path.dirname(item_info["item_path"])) == "playblasts":
                file_items.append(self._collect_playblast(parent_item,item_info))
            else:
                file_items.append(self._collect_file(parent_item,item_info))

        if not file_items:
            self.logger.warn("No files added, changed or deleted in Perforce for %s" % (folder.root_path,))

        return file_items

    def _collect_item_info(self, parent_item, path, frame_sequence=False, extra=None):
        """
        Process the supplied file path.

        :param parent_item: parent item instance
        :param path: Path to analyze
        :param frame_sequence: Treat the path as a part of a sequence
        :returns: The item that was created
        """

        # make sure the path is normalized. no trailing separator, separators
        # are appropriate for the current os, no double separators, etc.
        path = sgtk.util.ShotgunPath.normalize(path)

        # get info for the extension
        item_info = self._get_item_info(path)
        item_info["item_path"] = path
        item_info["parent"] = parent_item
        if extra:
            for key, value in extra.items():
                item_info[key] = value

        return item_info

    def _get_item_info(self, path):
        """
        Return a tuple of display name, item type, and icon path for the given
        filename.

        The method will try to identify the file as a common file type. If not,
        it will use the mimetype category. If the file still cannot be
        identified, it will fallback to a generic file type.

        :param path: The file path to identify type info for

        :return: A dictionary of information about the item to create::

            # path = "/path/to/some/file.0001.exr"

            {
                "item_type": "file.image.sequence",
                "type_display": "Rendered Image Sequence",
                "icon_path": "/path/to/some/icons/folder/image_sequence.png",
                "path": "/path/to/some/file.%04d.exr"
            }

        The item type will be of the form `file.<type>` where type is a specific
        common type or a generic classification of the file.
        """

        publisher = self.parent

        # extract the components of the supplied path
        file_info = publisher.util.get_file_path_components(path)
        extension = file_info["extension"]
        filename = file_info["filename"]
        priority = 0

        # default values used if no specific type can be determined
        type_display = "File"
        item_type = "file.unknown"

        # keep track if a common type was identified for the extension
        common_type_found = False

        icon_path = None

        # look for the extension in the common file type info dict
        for display in self.common_file_info:
            type_info = self.common_file_info[display]

            if extension in type_info["extensions"]:
                # found the extension in the common types lookup. extract the
                # item type, icon name.
                type_display = display
                item_type = type_info["item_type"]
                icon_path = type_info["icon"]
                priority = type_info["item_priority"]
                common_type_found = True
                break

        if not common_type_found:
            # no common type match. try to use the mimetype category. this will
            # be a value like "image/jpeg" or "video/mp4". we'll extract the
            # portion before the "/" and use that for display.
            (category_type, _) = mimetypes.guess_type(filename)

            if category_type:

                # mimetypes.guess_type can return unicode strings depending on
                # the system's default encoding. If a unicode string is
                # returned, we simply ensure it's utf-8 encoded to avoid issues
                # with toolkit, which expects utf-8
                category_type = six.ensure_str(category_type)

                # the category portion of the mimetype
                category = category_type.split("/")[0]

                type_display = "%s File" % (category.title(),)
                item_type = "file.%s" % (category,)
                icon_path = self._get_icon_path("%s.png" % (category,))

        # fall back to a simple file icon
        if not icon_path:
            icon_path = self._get_icon_path("file.png")

        # everything should be populated. return the dictionary
        return dict(
            item_type=item_type, type_display=type_display, icon_path=icon_path, extension=extension, item_priority=priority, children=[]
        )

    def _get_icon_path(self, icon_name, icons_folders=None):
        """
        Helper to get the full path to an icon.

        By default, the app's ``hooks/icons`` folder will be searched.
        Additional search paths can be provided via the ``icons_folders`` arg.

        :param icon_name: The file name of the icon. ex: "alembic.png"
        :param icons_folders: A list of icons folders to find the supplied icon
            name.

        :returns: The full path to the icon of the supplied name, or a default
            icon if the name could not be found.
        """

        # ensure the publisher's icons folder is included in the search
        app_icon_folder = os.path.join(self.disk_location, "icons")

        # build the list of folders to search
        if icons_folders:
            icons_folders.append(app_icon_folder)
        else:
            icons_folders = [app_icon_folder]

        # keep track of whether we've found the icon path
        found_icon_path = None

        # iterate over all the folders to find the icon. first match wins
        for icons_folder in icons_folders:
            icon_path = os.path.join(icons_folder, icon_name)
            if os.path.exists(icon_path):
                found_icon_path = icon_path
                break

        # supplied file name doesn't exist. return the default file.png image
        if not found_icon_path:
            found_icon_path = os.path.join(app_icon_folder, "file.png")

        return found_icon_path

    def _get_image_extensions(self):

        if not hasattr(self, "_image_extensions"):

            image_file_types = ["Photoshop Image", "Rendered Image", "Texture Image"]
            image_extensions = set()

            for image_file_type in image_file_types:
                image_extensions.update(
                    self.common_file_info[image_file_type]["extensions"]
                )

            # get all the image mime type image extensions as well
            mimetypes.init()
            types_map = mimetypes.types_map
            for (ext, mimetype) in types_map.items():
                if mimetype.startswith("image/"):
                    image_extensions.add(ext.lstrip("."))

            self._image_extensions = list(image_extensions)

        return self._image_extensions

    def _collect_playblast(self, parent_item, item_info):
        """
        Creates items for quicktime playblasts.

        Looks for a 'project_root' property on the parent item, and if such
        exists, look for movie files in a 'movies' subfolder.

        :param parent_item: Parent Item instance
        :param str project_root: The maya project root to search for playblasts
        """

        # do some early pre-processing to ensure the file is of the right
        # type. use the base class item info method to see what the item
        # type would be.
        path = item_info["item_path"]
        item_name = ".".join(os.path.basename(path).split(".")[:-1]) #os.path.basename(path).split('.')[:-1]

        if parent_item.name == "__root__":
            found_parent = parent_item
            for child in parent_item.children:
                
                if child.name == os.path.basename(path):
                    return
                if child.name.startswith(item_name):
                    found_parent = child

                    item = self._collect_file(found_parent, item_info)
                    if not item:
                        return None

                    # the item has been created. update the display name to include
                    # the an indication of what it is and why it was collected

                    publish_name = self.get_next_version_name(item,item.properties["path"])
                    item.properties["publish_name"] = publish_name       
                    item.name = f"(Review) {publish_name}"  

                    return item
        else:
            item = self._collect_file(parent_item, item_info)

            if not item:
                return None            

            publish_name = self.get_next_version_name(item,item.properties["path"])
            item.properties["publish_name"] = publish_name       
            item.name = f"(Review) {publish_name}"  

            return item

    def _process_hierarchy(self, item_infos, root_item):
        # Make sure our items are in descending order of priority
        item_infos = sorted(list(item_infos), key = lambda i: i['item_priority'], reverse=True)

        # Build the hierarchy
        for parent_item in list(item_infos):
            # Get all lower priority items remaining
            lower_items = [x for x in item_infos if x["item_priority"] < parent_item["item_priority"]]
            for lower_item in lower_items:
                # To capture partial matches, first see if the parent_item's name appears in this lower_item
                parent_item_name = os.path.basename(parent_item["item_path"]).split('.')[0]
                if parent_item_name in os.path.basename(lower_item["item_path"]):
                    # Now we need to see if there is a better (identical) match for this lower_item in the other potential parent items before adding it
                    other_parent_items = [os.path.basename(x["item_path"]).split('.')[0] for x in list(item_infos) if x["item_priority"] > lower_item["item_priority"]]
                    # Don't re-evaluate this parent_item
                    other_parent_items.remove(parent_item_name)
                    this_lower_item = os.path.basename(lower_item["item_path"]).split('.')[0]
                    better_item = False
                    for other_parent_item in other_parent_items:
                        if other_parent_item in this_lower_item and len(other_parent_item) > len(parent_item_name):
                            # There is a better parent match for this item, don't add it to this one
                            better_item = True
                        if better_item:
                            break

                    if not better_item:
                        # We didn't find a better match for lower_item, so append it to item
                        parent_item["children"].append(lower_item)
                        item_infos.remove(lower_item)

        return item_infos
    
    def _ensure_unique(self, path, parent_item):
        for existing_item in parent_item.descendants:
            if existing_item.properties["path"] == path:
                return False

        return True

    def get_next_version_name(self, item, path):
        # Increment version number based on how many versions
        self.publisher = self.parent

        # use the path's filename as the base publish name
        path_components = self.publisher.util.get_file_path_components(path)
        publish_name = path_components["filename"]

        # See how many prior versions there are
        filters = [
            ['entity', 'is', item.context.entity]
        ]

        prior_versions = self.publisher.shotgun.find("Version",filters,['code'])      

        regex = r"(" + re.escape(publish_name.split('.')[0]) + r"){1}(\.v\d)?\.\w*$"

        x = [i for i in prior_versions if re.match(regex,i['code'])]   

        # Set the publish name of this item as the next version
        version_number = len(x)+1     
        version_path = self.publisher.util.get_version_path(path,version_number)
        version_path_components = self.publisher.util.get_file_path_components(version_path)
        publish_name = version_path_components["filename"]  
        
        self.logger.info("Using prior version info to determine publish version.")
        self.logger.info("Publish name: %s" % (publish_name,))  

        return publish_name      

