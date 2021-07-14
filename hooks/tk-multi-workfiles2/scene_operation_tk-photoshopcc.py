# Copyright (c) 2015 Shotgun Software Inc.
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
from sgtk import TankError, LogManager

log = LogManager.get_logger(__name__)
HookBaseClass = sgtk.get_hook_baseclass()


class SceneOperation(HookBaseClass):
    """
    Hook called to perform an operation with the
    current scene
    """

    def execute(
        self,
        operation,
        file_path,
        context,
        parent_action,
        file_version,
        read_only,
        **kwargs
    ):
        """
        Main hook entry point

        :param operation:       String
                                Scene operation to perform

        :param file_path:       String
                                File path to use if the operation
                                requires it (e.g. open)

        :param context:         Context
                                The context the file operation is being
                                performed in.

        :param parent_action:   This is the action that this scene operation is
                                being executed for.  This can be one of:
                                - open_file
                                - new_file
                                - save_file_as
                                - version_up

        :param file_version:    The version/revision of the file to be opened.  If this is 'None'
                                then the latest version should be opened.

        :param read_only:       Specifies if the file should be opened read-only or not

        :returns:               Depends on operation:
                                'current_path' - Return the current scene
                                                 file path as a String
                                'reset'        - True if scene was reset to an empty
                                                 state, otherwise False
                                all others     - None
        """
        # run the base class operations
        base_class = super(SceneOperation, self).execute(operation, file_path, context,
                                                         parent_action, file_version,
                                                         read_only, **kwargs)
        # if the base_class returns false, go no further
        if not base_class:
            return False

        adobe = self.parent.engine.adobe

        if operation == "current_path":
            # return the current doc path
            doc = adobe.get_active_document_path()

            if doc is None:
                # new file?
                path = ""
            else:
                path = doc

            return path

        elif operation == "open":

            # open the specified script
            adobe.app.load(adobe.File(file_path))

        elif operation == "save":
            # save the current script
            doc = self._get_active_document()
            doc.save()

        elif operation == "save_as":
            # save current script as file_path
            doc = self._get_active_document()
            adobe.save_as(doc, file_path)
            self.parent.engine._PhotoshopCCEngine__add_to_context_cache(file_path, context)

        elif operation == "reset":
            # do nothing and indicate scene was reset to empty
            return True

        elif operation == "prepare_new":      
            # Get task data from Shotgun context
            adobe.app.preferences.rulerUnits = adobe.Units.PIXELS
            context_task = context.sgtk.shotgun.find_one("Task",
                                                [["id", "is", context.task["id"]]],
                                                ["sg_width", "sg_height", "sg_resolution"])
            
            task_width = context_task.get('sg_width')
            task_height = context_task.get('sg_height')
            task_dpi = context_task.get('sg_resolution')

            doc = adobe.app.documents.add(800 if task_width == None else task_width, 600 if task_height == None else task_height, 72 if task_dpi == None else task_dpi)

    def _get_active_document(self):
        """
        Returns the currently open document in Photoshop.
        Raises an exeption if no document is active.
        """
        doc = self.parent.engine.adobe.get_active_document()

        if not doc:
            raise TankError("There is no active document!")

        return doc
