# Copyright (c) 2019 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import sgtk

HookBaseClass = sgtk.get_hook_baseclass()


class PhotoshopCCDocumentPublishPlugin(HookBaseClass):
    """
    Plugin for publishing an open nuke studio project.

    This hook relies on functionality found in the base file publisher hook in
    the publish2 app and should inherit from it in the configuration. The hook
    setting for this plugin should look something like this::

        hook: "{self}/publish_file.py:{engine}/tk-multi-publish2/basic/publish_document.py"

    """

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
        base_settings = super(PhotoshopCCDocumentPublishPlugin, self).settings or {}

        # settings specific to this class
        photoshop_publish_settings = {
            "Publish Template": {
                "type": "template",
                "default": None,
                "description": "Template path for published work files. Should"
                "correspond to a template defined in "
                "templates.yml.",
            }
        }

        # update the base settings
        base_settings.update(photoshop_publish_settings)

        return base_settings

    @property
    def item_filters(self):
        """
        List of item types that this plugin is interested in.

        Only items matching entries in this list will be presented to the
        accept() method. Strings can contain glob patters such as *, for example
        ["maya.*", "file.maya"]
        """
        return super(PhotoshopCCDocumentPublishPlugin, self).item_filters + ["photoshop.document"]

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
        if item.type_spec == "photoshop.document":
            document = item.properties.get("document")
            if not document:
                self.logger.warn("Could not determine the document for item")
                return {"accepted": False}

            path = _document_path(document)

            if not path:
                # the document has not been saved before (no path determined).
                # provide a save button. the document will need to be saved before
                # validation will succeed.
                self.logger.warn(
                    "The Photoshop document '%s' has not been saved." % (document.name,),
                    extra=_get_save_as_action(document),
                )

            self.logger.info(
                "Photoshop '%s' plugin accepted document: %s." % (self.name, document.name)
            )
            return {"accepted": True, "checked": True}
        else:
            super(PhotoshopCCDocumentPublishPlugin, self).accept(settings, item)

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

        if item.type_spec == "photoshop.document":
            publisher = self.parent
            engine = publisher.engine
            document = item.properties["document"]
            path = _document_path(document)

            # ---- ensure the document has been saved

            if not path:
                # the document still requires saving. provide a save button.
                # validation fails.
                error_msg = "The Photoshop document '%s' has not been saved." % (
                    document.name,
                )
                self.logger.error(error_msg, extra=_get_save_as_action(document))
                raise Exception(error_msg)

            # ---- check the document against any attached work template

            # get the path in a normalized state. no trailing separator,
            # separators are appropriate for current os, no double separators,
            # etc.
            path = sgtk.util.ShotgunPath.normalize(path)

            # if the document item has a known work template, see if the path
            # matches. if not, warn the user and provide a way to save the file to
            # a different path
            work_template = item.properties.get("work_template")
            if work_template:
                if not work_template.validate(path):
                    self.logger.warning(
                        "The current document does not match the configured work "
                        "template.",
                        extra={
                            "action_button": {
                                "label": "Save File",
                                "tooltip": "Save the current Photoshop document"
                                "to a different file name",
                                # will launch wf2 if configured
                                "callback": _get_save_as_action(document),
                            }
                        },
                    )
                else:
                    self.logger.debug("Work template configured and matches document path.")
            else:
                self.logger.debug("No work template configured.")

            item.properties["path"] = path

        # run the base class validation
        return super(PhotoshopCCDocumentPublishPlugin, self).validate(settings, item)

    def publish(self, settings, item):
        """
        Executes the publish logic for the given item and settings.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """
        if item.type_spec == "photoshop.document":
            publisher = self.parent
            engine = publisher.engine
            document = item.properties["document"]
            path = _document_path(document)

            # get the path in a normalized state. no trailing separator, separators
            # are appropriate for current os, no double separators, etc.
            path = sgtk.util.ShotgunPath.normalize(path)

            # ensure the document is saved
            engine.save(document)

            # update the item with the saved document path
            item.properties["path"] = path

        # let the base class register the publish
        super(PhotoshopCCDocumentPublishPlugin, self).publish(settings, item)

def _get_save_as_action(document):
    """
    Simple helper for returning a log action dict for saving the document
    """

    engine = sgtk.platform.current_engine()

    # default save callback
    def callback(): return engine.save_as(document)

    # if workfiles2 is configured, use that for file save
    if "tk-multi-workfiles2" in engine.apps:
        app = engine.apps["tk-multi-workfiles2"]
        if hasattr(app, "show_file_save_dlg"):
            callback = app.show_file_save_dlg

    return {
        "action_button": {
            "label": "Save As...",
            "tooltip": "Save the current document",
            "callback": callback,
        }
    }

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
