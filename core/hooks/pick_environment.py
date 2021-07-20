# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Hook which chooses an environment file to use based on the current context.
"""

import sgtk

logger = sgtk.platform.get_logger(__name__)


class PickEnvironment(sgtk.Hook):
    def execute(self, context, **kwargs):
        """
        The default implementation assumes there are three environments, called shot, asset
        and project, and switches to these based on entity type.
        """

        if context.source_entity:
            if context.source_entity["type"] == "Version":
                return "version"
            elif context.source_entity["type"] == "PublishedFile":
                return "publishedfile"

        if context.project is None:
            # Our context is completely empty. We're going into the site context.
            return "site"

        if context.entity is None:
            # We have a project but not an entity.
            return "project"

        if context.entity and context.step is None:
            # We have an entity but no step.            
            if context.entity["type"] == "Asset":
                context_entity = context.sgtk.shotgun.find_one("Asset",
                                                               [["id", "is", context.entity["id"]]],
                                                               ["sg_asset_parent"])

                if context_entity.get("sg_asset_parent"):
                    return "asset_child"

                return "asset"
            elif context.entity["type"] == "CustomEntity01":
                return "env_asset"  
            elif context.entity["type"] == "CustomEntity03":
                return "pub_asset"                        

        if context.entity and context.step:
            # We have a step and an entity.
            master_token = "_"

            if context.step["name"]== "Master":
                master_token = "_master_"            

            if context.entity["type"] == "Asset":
                context_entity = context.sgtk.shotgun.find_one("Asset",
                                                               [["id", "is", context.entity["id"]]],
                                                               ["sg_asset_parent"])

                if context_entity.get("sg_asset_parent"):
                    return "asset_child%sstep" % (master_token)

                return "asset%sstep" % (master_token)
            elif context.entity["type"] == "CustomEntity01":
                return "env_asset%sstep" % (master_token)    
            elif context.entity["type"] == "CustomEntity03":
                return "pub_asset_step"                    

        return None
