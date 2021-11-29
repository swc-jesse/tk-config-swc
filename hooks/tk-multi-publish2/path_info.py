# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from tank.util import sgre as re

import sgtk

HookBaseClass = sgtk.get_hook_baseclass()

# ---- globals

# a regular expression used to extract the version number from the file.
# this implementation assumes the version number is of the form 'v###'
# coming just before an optional extension in the file/folder name and just
# after a '.', '_', or '-'.
VERSION_REGEX = re.compile(r"(.*)([._-])v(\d+)\.?([^.]+)?$", re.IGNORECASE)

# a regular expression used to extract the frame number from the file.
# this implementation assumes the version number is of the form '.####'
# coming just before the extension in the filename and just after a '.', '_',
# or '-'.
FRAME_REGEX = re.compile(r"(.*)([._-])(\d+)\.([^.]+)$", re.IGNORECASE)


class BasicPathInfo(HookBaseClass):
    """
    Methods for basic file path parsing.
    """

    def get_publish_name(self, path, sequence=False):
        """
        Given a file path, return the display name to use for publishing.

        Typically, this is a name where the path and any version number are
        removed in order to keep the publish name consistent as subsequent
        versions are published.

        Example::

            # versioned file. remove the version
            in: /path/to/the/file/scene.v001.ma
            out: scene.ma

            # image sequence. replace the frame number with #s
            in: /path/to/the/file/my_file.001.jpg
            out: my_file.###.jpg

        :param path: The path to a file, likely one to be published.
        :param sequence: If True, treat the path as a sequence name and replace
            the frame number with placeholder

        :return: A publish display name for the provided path.
        """

        publisher = self.parent

        logger = publisher.logger
        logger.debug("Getting publish name for path: %s ..." % (path,))

        path_info = publisher.util.get_file_path_components(path)
        filename = path_info["filename"]

        frame_pattern_match = re.search(FRAME_REGEX, filename)

        if frame_pattern_match and sequence:
            # found a frame number, meplace it with #s
            prefix = frame_pattern_match.group(1)
            frame_sep = frame_pattern_match.group(2)
            frame = frame_pattern_match.group(3)
            display_str = "#" * len(frame)
            extension = frame_pattern_match.group(4) or ""
            publish_name = "%s%s%s.%s" % (prefix, frame_sep, display_str, extension)
        else:
            publish_name = filename

        logger.debug("Returning publish name: %s" % (publish_name,))
        return publish_name