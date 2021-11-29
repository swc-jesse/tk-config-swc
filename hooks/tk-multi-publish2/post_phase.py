# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import pprint
import os
import sgtk
from sgtk.platform.qt import QtCore, QtGui
from datetime import datetime, timedelta
from time import sleep

HookBaseClass = sgtk.get_hook_baseclass()
TK_FRAMEWORK_PERFORCE_NAME = "tk-framework-perforce_v0.x.x"

def qwaiter(t):
    end = datetime.now() + timedelta(milliseconds=t)
    while datetime.now() < end:
        QtGui.QApplication.processEvents()

class ChangeSubmitSignaller(QtCore.QObject):
    """
    Create signaller class for Sync Worker, required for using signals due to QObject inheritance
    """
    submission_response = QtCore.Signal(list)

class ChangeSubmitWorker(QtCore.QRunnable):

    p4 = None
    fw = None

    def __init__(self, fw, p4, change):
        super(ChangeSubmitWorker, self).__init__()
        self.signaller = ChangeSubmitSignaller()
        self.submission_response = self.signaller.submission_response
        self.fw = fw
        self.p4 = p4
        self.change = change


    @QtCore.Slot()
    def run(self):
        submission = self.fw.util.submit_change(self.p4, self.change)
        self.submission_response.emit(submission)

class PostPhaseHook(HookBaseClass):
    """
    This hook defines methods that are executed after each phase of a publish:
    validation, publish, and finalization. Each method receives the publish
    tree instance being used by the publisher, giving full control to further
    curate the publish tree including the publish items and the tasks attached
    to them. See the :class:`PublishTree` documentation for additional details
    on how to traverse the tree and manipulate it.
    """
    eta = ""
    description = ""
    percent_complete = 0.0
    submission = []
    total_size = ""
    transfer_rate = ""

    thread = QtCore.QThreadPool.globalInstance()
    thread.setMaxThreadCount(1)

    def update_progress_description(self, description):
        self.description = os.path.basename(description)

    def update_percent_complete(self, percent):
        self.percent_complete = percent

    def update_total_size(self, size):
        self.total_size = size

    def update_transfer_rate(self, rate):
        self.transfer_rate = rate

    def update_progress_eta(self, eta):
        self.eta = eta
        self.logger.info("Submitting {}<br>[ <b>{}</b>% of {}, {}] {}".format(self.description, 
                                                                       int(self.percent_complete), 
                                                                       self.total_size,
                                                                       eta.split('.')[0],
                                                                       self.transfer_rate
                                                                       ))

    def update_submission_response(self, submission):
        self.submission = submission
    

    def post_publish(self, publish_tree):

        # See if anything was Published to Perforce
        do_post_publish = False
        for item in publish_tree:

            if item.properties.get('publish_data'):
                do_post_publish = True
        
            if do_post_publish:
                break

        if do_post_publish:
            self.logger.debug("Starting Post-publish phase.")
            self.publisher = self.parent

            # Make the p4 connection
            self.p4_fw = self.load_framework(TK_FRAMEWORK_PERFORCE_NAME)
            self.logger.debug("Perforce framework loaded.")

            p4 = self.p4_fw.connection.connect(progress=True)
            self.logger.debug("Perforce connection made.")

            # create a new changelist for all files being published:
            self.logger.info("Creating new Perforce changelist...")

            # collect descriptions from Publish Items to supply P4 with change description
            change_descriptions = "\n".join(
                list(set(["- {}".format(item.description) for item in publish_tree
                    if item.description
                ]))
            )

            new_change = self.p4_fw.util.create_change(p4, change_descriptions)
            # NOTE: new_change just returns the id of the change

            change_items = []

            for item in publish_tree:

                if item.properties.get('publish_data'):

                    path = item.properties.get("path")

                    self.logger.info("Ensuring file is checked out...")
                    try:
                        self.p4_fw.util.open_file_for_edit(p4, path, add_if_new=True)
                    except self.p4_fw.util.P4InvalidFileNameException as e:
                        self.logger.error("Illegal filename for use in Perforce", extra={
                            "action_show_more_info": {
                                "label": "Error Details",
                                "tooltip": pprint.pformat(str(e)),
                                "text": "<pre>%s</pre>" %pprint.pformat(str(e)),
                                }
                            }
                        )
                        break

                    # depo_paths = self.p4_fw.util.client_to_depot_paths(p4, path)
                    # self.logger.info("Depo paths: {}".format(depo_paths))
                    # NOTE: This returns an empty string for new files. Presumably
                    # this function only works for files already in the depo.

                    # and add the file to this change:
                    self.logger.info("Adding the file to the change: {}".format(path))
                    self.p4_fw.util.add_to_change(p4, new_change, path)
                    # NOTE: for some reason this is not adding anything to the change
                    # and I cannot figure out why.

                    change_items.append(item)

            for result in p4.run('files', '@=' + new_change):
                # NOTE: well this shit doesnt work at all.

                self.logger.debug(
                    "Perforce Change details...",
                    extra={
                        "action_show_more_info": {
                            "label": "P4 Change details",
                            "tooltip": "Show the Perforce Change details before check-in",
                            "text": "<pre>%s</pre>".format(pprint.pformat(result)),
                        }
                    },
                )

            # submit the change:
            self.logger.info("Submitting the change...")


            # submit the change using a thread
            submit_worker = ChangeSubmitWorker(self.p4_fw, p4, new_change)

            # connect progress-specific signals
            submit_worker.p4.progress.description.connect(self.update_progress_description)
            submit_worker.p4.progress.percent_done.connect(self.update_percent_complete)
            submit_worker.p4.progress.time_remaining.connect(self.update_progress_eta)
            submit_worker.p4.progress.transfer_rate.connect(self.update_transfer_rate)
            submit_worker.p4.progress.total_size.connect(self.update_total_size)

            # connect worker-specific signal
            submit_worker.submission_response.connect(self.update_submission_response)

            # send worker to thread and start
            self.thread.start(submit_worker)

            # await the submission being returned from the worker, but dont block the UI.
            while not self.submission:
                qwaiter(1000)


            self.logger.debug(
                "Perforce Submission data...",
                extra={
                    "action_show_more_info": {
                        "label": "P4 Submission",
                        "tooltip": "Show the complete Perforce Submission data",
                        "text": "<pre>{}</pre>".format(pprint.pformat(self.submission)),
                    }
                },
            )

            changed_files = [i for i in [s for s in self.submission if isinstance(s, dict)] if i.get('depotFile')]
            """
            [{'action': 'edit',
            'depotFile': '//deva/Tool/ScorchedEarth/ToolCategory/ToolTestAsset/deva_ScorchedEarth_ToolTestAsset_concept.psd',
            'rev': '4'},
            {'action': 'edit',
            'depotFile': '//deva/Tool/ScorchedEarth/ToolCategory/ToolTestAsset/deva_ScorchedEarth_ToolTestAsset_concept_alt.psd',
            'rev': '6'}]
            """

            submitted_change = next((int(i['submittedChange']) for i in [s for s in self.submission if isinstance(s, dict)] if i.get('submittedChange')), None)
            """
            {'submittedChange': '92'}
            """

            for item in publish_tree:

                # Iterate thru the submission and update each items publish_data with
                # the perforce data (version_number, sg_p4_change_number, sg_p4_depo_path)
                if item in change_items:
                    item = self._update_publish_data(p4, item, changed_files, submitted_change)

                # Find and link submitted versions to published files
            self._update_version_data(publish_tree)

            self._update_thumbnails(publish_tree)

    def _update_publish_data(self, p4, item, changed_files, submitted_change):
        """
        Updates Perforce data and Upstream / Downstream files based on Parent / Child
        relationships in the item.

        :param p4: A Perforce instance
        :param item: The PublishItem we're interested in
        :param changed_files: A list of changed file dictionaries
        :param submitted_change: The Perforce changelist that was submitted
        """            
        depot_path = self.p4_fw.util.client_to_depot_paths(p4, item.properties.get("path"))[0]
        self.logger.debug("depot_path = {}".format(depot_path))
        
        change_data = [i for i in changed_files if i['depotFile'] == depot_path][0]

        if change_data:

            # use the p4 revision number as the version number
            item.properties.publish_data["version_number"] = int(change_data["rev"])

            # attach the p4 data to the "sg_fields" dict which updates the published file entry in SG
            item.properties.publish_data["sg_fields"]["sg_p4_depo_path"] = change_data["depotFile"]
            item.properties.publish_data["sg_fields"]["sg_p4_change_number"] = submitted_change
            if hasattr(item.parent.properties, "sg_publish_data"):
                item.properties.publish_data["sg_fields"]["upstream_published_files"] = [item.parent.properties.sg_publish_data]

            # Register the Publish
            item.properties.sg_publish_data = sgtk.util.register_publish(**item.properties.publish_data)

            # update the published file 'code' field to match Perforce rev formating (filename.ext#rev) so we can tell them apart in SG
            update_data = {'code': "{}#{}".format(item.properties.sg_publish_data['code'], change_data["rev"])}
            self.publisher.shotgun.update("PublishedFile", item.properties.sg_publish_data['id'], update_data)   

            self.logger.info("Publish registered!")
            self.logger.debug(
                "ShotGrid Publish data...",
                extra={
                    "action_show_more_info": {
                        "label": "ShotGrid Publish Data",
                        "tooltip": "Show the complete ShotGrid Publish Entity dictionary",
                        "text": "<pre>{}</pre>".format(pprint.pformat(item.properties.sg_publish_data)),
                    }
                },
            )  

        return item   

    def _update_version_data(self, publish_tree):
        """
        Walks down the Publish Tree and updates version data.

        :param publish_tree: PublishTree instance
        """        
        for item in publish_tree:
            # If this is a published file
            if "sg_publish_data" in item.properties:
                # And if there is no version linked
                if not "version" in item.properties.sg_publish_data:
                    # See if we have our own published version data from earlier
                    if "sg_version_data" in item.properties:
                        version = item.properties["sg_version_data"]
                        update_data = {'version':version}

                        self.publisher.shotgun.update("PublishedFile", item.properties.sg_publish_data['id'], update_data)
                        item.properties.sg_publish_data.update(update_data)   
                    # Otherwise see if our parent has any version data we can use
                    elif "sg_publish_data" in item.parent.properties:
                        if "version" in item.parent.properties.sg_publish_data:
                            update_data = {'version':item.parent.properties.sg_publish_data['version']}
                            self.publisher.shotgun.update("PublishedFile", item.properties.sg_publish_data['id'], update_data)
                            item.properties.sg_publish_data.update(update_data)
            # Or if this is only a version with no published file
            elif "sg_version_data" in item.properties:
                # And our parent is a published file
                 if "sg_publish_data" in item.parent.properties:
                    # And our parent has no version linked, link ourselves now
                    if not "version" in item.parent.properties.sg_publish_data:
                        version = item.properties["sg_version_data"]
                        update_data = {'version':version}

                        self.publisher.shotgun.update("PublishedFile", item.parent.properties.sg_publish_data['id'], update_data)
                        item.parent.properties.sg_publish_data.update(update_data)

    def _update_thumbnails(self, publish_tree):
        for item in publish_tree:
            # Only update the thumbnail if one hasn't been set explicitly
            if "sg_publish_data" in item.properties and not item.thumbnail:
                if "version" in item.properties.sg_publish_data:
                    version = item.properties.sg_publish_data["version"]

                    # Share thumbnail from the linked version, but it needs time to upload.
                    # If it's not ready yet, sleep and wait for the upload to finish 
                    sleep_time = 2
                    num_retries = 4

                    for x in range(0, num_retries):  
                        str_error = None
                        try:
                            thumb1 = self.publisher.shotgun.share_thumbnail(entities=[item.properties.sg_publish_data],source_entity=version)
                            thumb2 = self.publisher.shotgun.share_thumbnail(entities=[item.properties.sg_publish_data],source_entity=version,filmstrip_thumbnail=True)
                        except Exception as e:
                            str_error = str(e)
                            self.logger.info("Waiting for Thumbnail...")
                            pass

                        if str_error:
                            sleep(sleep_time)  # wait before trying to fetch the data again
                            sleep_time *= 2  
                        else:
                            self.logger.info("Thumbnail shared successfully!")
                            break
                    
