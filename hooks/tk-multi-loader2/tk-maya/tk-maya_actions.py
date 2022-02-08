# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Hook that loads defines all the available actions, broken down by publish type.
"""

import glob
import os
import re
import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMaya as om
import sgtk

from tank_vendor import six

HookBaseClass = sgtk.get_hook_baseclass()


class MayaOverrideActions(HookBaseClass):
    ##############################################################################################################
    # helper methods which can be subclassed in custom hooks to fine tune the behaviour of things

    def _create_reference(self, path, sg_publish_data):
        """
        Create a reference with the same settings Maya would use
        if you used the create settings dialog.

        :param path: Path to file.
        :param sg_publish_data: Shotgun data dictionary with all the standard publish fields.
        """
        if not os.path.exists(path):
            raise Exception("File not found on disk - '%s'" % path)

        # Emulate Maya's default behavior for building the namespace from the filename
        uri = om.MURI(f'/{sg_publish_data.get("name")}')
        namespace = uri.getFileName(False)

        # Now create the reference object in Maya.
        cmds.file(
            path,
            reference=True,
            loadReferenceDepth="all",
            mergeNamespacesOnClash=False,
            namespace=namespace,
        )

    def _do_import(self, path, sg_publish_data):
        """
        Create a reference with the same settings Maya would use
        if you used the create settings dialog.

        :param path: Path to file.
        :param sg_publish_data: Shotgun data dictionary with all the standard publish fields.
        """
        if not os.path.exists(path):
            raise Exception("File not found on disk - '%s'" % path)

        # Emulate Maya's default behavior for building the namespace from the filename
        uri = om.MURI(f'/{sg_publish_data.get("name")}')
        namespace = uri.getFileName(False)

        # perform a more or less standard maya import, putting all nodes brought in into a specific namespace
        cmds.file(
            path,
            i=True,
            renameAll=True,
            namespace=namespace,
            loadReferenceDepth="all",
            preserveReferences=True,
        )

    def _create_texture_node(self, path, sg_publish_data):
        """
        Create a file texture node for a texture

        :param path:             Path to file.
        :param sg_publish_data:  Shotgun data dictionary with all the standard publish fields.
        :returns:                The newly created file node
        """
        file_node = cmds.shadingNode("file", asTexture=True)
        cmds.setAttr("%s.fileTextureName" % file_node, path, type="string")
        return file_node

    def _create_udim_texture_node(self, path, sg_publish_data):
        """
        Create a file texture node for a UDIM (Mari) texture

        :param path:             Path to file.
        :param sg_publish_data:  Shotgun data dictionary with all the standard publish fields.
        :returns:                The newly created file node
        """
        # create the normal file node:
        file_node = self._create_texture_node(path, sg_publish_data)
        if file_node:
            # path is a UDIM sequence so set the uv tiling mode to 3 ('UDIM (Mari)')
            cmds.setAttr("%s.uvTilingMode" % file_node, 3)
            # and generate a preview:
            mel.eval("generateUvTilePreview %s" % file_node)
        return file_node

    def _create_image_plane(self, path, sg_publish_data):
        """
        Create a file texture node for a UDIM (Mari) texture

        :param path: Path to file.
        :param sg_publish_data: Shotgun data dictionary with all the standard
            publish fields.
        :returns: The newly created file node
        """

        app = self.parent
        has_frame_spec = False

        # replace any %0#d format string with a glob character. then just find
        # an existing frame to use. example %04d => *
        frame_pattern = re.compile("(%0\dd)")
        frame_match = re.search(frame_pattern, path)
        if frame_match:
            has_frame_spec = True
            frame_spec = frame_match.group(1)
            glob_path = path.replace(frame_spec, "*")
            frame_files = glob.glob(glob_path)
            if frame_files:
                path = frame_files[0]
            else:
                app.logger.error(
                    "Could not find file on disk for published file path %s" % (path,)
                )
                return

        # create an image plane for the supplied path, visible in all views
        (img_plane, img_plane_shape) = cmds.imagePlane(
            fileName=path, showInAllViews=True
        )
        app.logger.debug("Created image plane %s with path %s" % (img_plane, path))

        if has_frame_spec:
            # setting the frame extension flag will create an expression to use
            # the current frame.
            cmds.setAttr("%s.useFrameExtension" % (img_plane_shape,), 1)

    def _get_maya_version(self):
        """
        Determine and return the Maya version as an integer

        :returns:    The Maya major version
        """
        if not hasattr(self, "_maya_major_version"):
            self._maya_major_version = 0
            # get the maya version string:
            maya_ver = cmds.about(version=True)
            # handle a couple of different formats: 'Maya XXXX' & 'XXXX':
            if maya_ver.startswith("Maya "):
                maya_ver = maya_ver[5:]
            # strip of any extra stuff including decimals:
            major_version_number_str = maya_ver.split(" ")[0].split(".")[0]
            if major_version_number_str and major_version_number_str.isdigit():
                self._maya_major_version = int(major_version_number_str)
        return self._maya_major_version
