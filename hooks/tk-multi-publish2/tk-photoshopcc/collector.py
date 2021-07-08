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

HookBaseClass = sgtk.get_hook_baseclass()


class PhotoshopCCSceneCollector(HookBaseClass):
    """
    Collector that operates on the current photoshop document. Should inherit
    from the basic collector hook.
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
        self._common_file_info = super.common_file_info()

        return self._common_file_info

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
        collector_settings = super(PhotoshopCCSceneCollector, self).settings or {}

        # settings specific to this collector
        photoshop_session_settings = {
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
        collector_settings.update(photoshop_session_settings)

        return collector_settings

    def process_current_session(self, settings, parent_item):
        """
        Analyzes the open documents in Photoshop and creates publish items
        parented under the supplied item.

        :param dict settings: Configured settings for this collector
        :param parent_item: Root item instance
        """

        # go ahead and build the path to the icon for use by any documents
        icon_path = os.path.join(self.disk_location, os.pardir, os.pardir, os.pardir, "icons", "photoshop.png")

        publisher = self.parent
        engine = publisher.engine
        document = engine.adobe.get_active_document()

        if document:
            active_doc_name = document.name
        else:
            engine.logger.debug("No active document found.")
            active_doc_name = None

        # Attempt to retrieve a configured work template. We can attach
        # it to the collected project items.
        work_template_setting = settings.get("Work Template")
        work_template = None
        if work_template_setting:
            work_template = publisher.engine.get_template_by_name(
                work_template_setting.value
            )

        # FIXME: begin temporary workaround
        # we use different logic here only because we don't have proper support
        # for multi context workflows when templates are in play. So if we have
        # a work template configured, for now we'll only collect the current,
        # active document. Once we have proper multi context support, we can
        # remove this.
        if work_template:
            # same logic as the loop below but only processing the active doc
            if not document:
                return
            document_item = parent_item.create_item(
                "photoshop.document", "Photoshop Image", document.name
            )
            self.logger.info("Collected Photoshop document: %s" % (document.name))
            document_item.set_icon_from_path(icon_path)
            document_item.thumbnail_enabled = False
            document_item.properties["document"] = document
            path = _document_path(document)
            if path:
                document_item.set_thumbnail_from_path(path)
            document_item.properties["work_template"] = work_template
            self.logger.debug("Work template defined for Photoshop collection.")
            if path:
                self.logger.info("Looking for additional files at " + str(path))
            return
        # FIXME: end temporary workaround

        # remember the current document. we need to switch documents while
        # collecting in order to get the proper context associated with each
        # item created.
        current_document = engine.adobe.get_active_document()

        # iterate over all open documents and add them as publish items
        for document in engine.adobe.app.documents:

            # ensure the document is the current one
            engine.adobe.app.activeDocument = document

            # create a publish item for the document
            document_item = parent_item.create_item(
                "photoshop.document", "Photoshop Image", document.name
            )

            document_item.set_icon_from_path(icon_path)

            # Disable thumbnail creation for Photoshop documents. For the
            # default workflow, the thumbnail will be auto-updated after the
            # version creation plugin runs.
            document_item.thumbnail_enabled = False

            # add the document object to the properties so that the publish
            # plugins know which open document to associate with this item
            document_item.properties["document"] = document

            doc_name = document.name
            self.logger.info("Collected Photoshop document: %s" % (doc_name))

            # enable the active document and expand it. other documents are
            # collapsed and disabled.
            if active_doc_name and doc_name == active_doc_name:
                document_item.expanded = True
                document_item.checked = True
            elif active_doc_name:
                # there is an active document, but this isn't it. collapse and
                # disable this item
                document_item.expanded = False
                document_item.checked = False

            path = _document_path(document)

            if path:
                # try to set the thumbnail for display. won't display anything
                # for psd/psb, but others should work.
                document_item.set_thumbnail_from_path(path)

            # store the template on the item for use by publish plugins. we
            # can't evaluate the fields here because there's no guarantee the
            # current session path won't change once the item has been created.
            # the attached publish plugins will need to resolve the fields at
            # execution time.
            if work_template:
                document_item.properties["work_template"] = work_template
                self.logger.debug("Work template defined for Photoshop collection.")

        # reset the original document to restore the state for the user
        engine.adobe.app.activeDocument = current_document

    def process_file(self, settings, parent_item, path):
        """
        Analyzes the given file and creates one or more items
        to represent it.
        :param dict settings: Configured settings for this collector
        :param parent_item: Root item instance
        :param path: Path to analyze
        :returns: The main item that was created, or None if no item was created
            for the supplied path
        """

        # handle files and folders differently
        if os.path.isdir(path):
            self._collect_folder(parent_item, path)
            return None
        else:
            return self._collect_file(parent_item, path)

    def _collect_file(self, parent_item, path, frame_sequence=False):
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

        publisher = self.parent

        # get info for the extension
        item_info = self._get_item_info(path)
        item_type = item_info["item_type"]
        type_display = item_info["type_display"]
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

        # create and populate the item
        file_item = parent_item.create_item(item_type, type_display, display_name)
        file_item.set_icon_from_path(item_info["icon_path"])

        # Collect a sub item
        sub_item = file_item.create_item(item_type, type_display, display_name + "_sub")
        sub_item.set_icon_from_path(item_info["icon_path"])
        sub_item.properties["path"] = evaluated_path
        # Collect a sub item
        subsub_item = sub_item.create_item(
            item_type, type_display, display_name + "_evenmoresub"
        )
        subsub_item.set_icon_from_path(item_info["icon_path"])
        subsub_item.properties["path"] = evaluated_path

        # if the supplied path is an image, use the path as the thumbnail.
        if item_type.startswith("file.image") or item_type.startswith("file.texture"):
            file_item.set_thumbnail_from_path(path)

            # disable thumbnail creation since we get it for free
            file_item.thumbnail_enabled = False

        # all we know about the file is its path. set the path in its
        # properties for the plugins to use for processing.
        file_item.properties["path"] = evaluated_path

        if is_sequence:
            # include an indicator that this is an image sequence and the known
            # file that belongs to this sequence
            file_item.properties["sequence_paths"] = [path]

        self.logger.info("Collected file: %s" % (evaluated_path,))

        return file_item

    def _collect_folder(self, parent_item, folder):
        """
        Process the supplied folder path.
        :param parent_item: parent item instance
        :param folder: Path to analyze
        :returns: The item that was created
        """

        # make sure the path is normalized. no trailing separator, separators
        # are appropriate for the current os, no double separators, etc.
        folder = sgtk.util.ShotgunPath.normalize(folder)

        publisher = self.parent
        img_sequences = publisher.util.get_frame_sequences(
            folder, self._get_image_extensions()
        )

        file_items = []

        for (image_seq_path, img_seq_files) in img_sequences:

            # get info for the extension
            item_info = self._get_item_info(image_seq_path)
            item_type = item_info["item_type"]
            type_display = item_info["type_display"]

            # the supplied image path is part of a sequence. alter the
            # type info to account for this.
            type_display = "%s Sequence" % (type_display,)
            item_type = "%s.%s" % (item_type, "sequence")
            icon_name = "image_sequence.png"

            # get the first frame of the sequence. we'll use this for the
            # thumbnail and to generate the display name
            img_seq_files.sort()
            first_frame_file = img_seq_files[0]
            display_name = publisher.util.get_publish_name(
                first_frame_file, sequence=True
            )

            # create and populate the item
            file_item = parent_item.create_item(item_type, type_display, display_name)
            icon_path = self._get_icon_path(icon_name)
            file_item.set_icon_from_path(icon_path)

            # use the first frame of the seq as the thumbnail
            file_item.set_thumbnail_from_path(first_frame_file)

            # disable thumbnail creation since we get it for free
            file_item.thumbnail_enabled = False

            # all we know about the file is its path. set the path in its
            # properties for the plugins to use for processing.
            file_item.properties["path"] = image_seq_path
            file_item.properties["sequence_paths"] = img_seq_files

            self.logger.info("Collected file: %s" % (image_seq_path,))

            file_items.append(file_item)

        if not file_items:
            self.logger.warn("No image sequences found in: %s" % (folder,))

        return file_items

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
            item_type=item_type, type_display=type_display, icon_path=icon_path,
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

def _document_path(document):
    """
    Returns the path on disk to the supplied document. May be ``None`` if the
    document has not been saved.
    """

    try:
        path = document.fullName.fsName
    except Exception:
        path = None

    return path