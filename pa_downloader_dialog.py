""" this file contains GUI logic for the main plugin form. The template file was created by the plugin builder """
import os

from PyQt5.QtCore import Qt
from qgis.PyQt import QtWidgets
from qgis.PyQt import uic
from qgis.core import QgsProject
from qgis.utils import QgsMessageLog

from .pa_downloader_workers import Thread, get_sensor_list
from .pa_downloader_dialog_settings import PurpleAirDownloaderDialogSettings
from .pa_downloader_heplers import get_current_map_extent, get_layer_extent_by_index, validate_input_coordinates, \
    read_settings, check_api_key

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'pa_downloader_dialog_base.ui'))


class PurpleAirDownloaderDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(PurpleAirDownloaderDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.settings_pb.clicked.connect(self.show_settings_dialog)
        self.download_pb.clicked.connect(self.download)
        self.refresh_layers_pb.clicked.connect(self.refresh_layer_list)
        self.use_le_rb.toggled.connect(self.refresh_layer_list)
        self.stop_pb.clicked.connect(self.stop_download)

    def show_settings_dialog(self):
        """
        this method shows a child dialog when user clicks settings button
        """
        # reading settings from the settings file
        settings = read_settings()
        self.dialog = PurpleAirDownloaderDialogSettings()
        self.dialog.setupUi(self.dialog)
        """
        When user opens the dialog, these two lines update the empty setting values with these read from settings file
        they should be better placed in the __init__ function of the PurpleAirDownloaderDialogSettings class
        but for some reason they do not update the dialog fields. So I have to put them below
        """
        self.dialog.pa_api_key_le.setText(settings['api_key'])
        self.dialog.proc_num_sb.setValue(int(settings['proc_num']))
        self.dialog.show()

    def download(self):
        """
        this method invokes when the user clicks the Download button. It checks radio buttons, runs functions to
        retrieve current extent or to validate input values. If the validation passed, the function creates a child
        QTread(we need this to avoid freezing the GUI) and that child QTread in turn runs the multi-treading code to
        download json data for the individual sensors.
        """
        # Let's check our API key first, and exit if the key is not valid
        settings = read_settings()
        if not check_api_key(settings['api_key']):
            QtWidgets.QMessageBox.critical(None, "Invalid API key",
                                           "Purpleair.com API key is invalid. Please update it in the settings")
            return None
        # retrieve the input parameters such as a start and an end dates.
        start_date = self.start_date_dateEdit.date().toString(Qt.ISODate)
        end_date = self.end_date_dateEdit.date().toString(Qt.ISODate)
        # outdoor and indoor sensors
        sensor_type = self.sensor_type_qb.currentIndex()

        # if the user wants to download sensor data in a current extent
        if self.use_current_extent_rb.isChecked():
            # check if we have any layers in the project, so the user knows the location they want to download
            if not QgsProject.instance().mapLayers().values():
                QtWidgets.QMessageBox.critical(None, "No layers",
                                               "No layers in the current project. Can't get current extent.")
                return None
            else:
                # retrieve the current extent of the map
                input_coords = get_current_map_extent()
                QgsMessageLog.logMessage(f"Current extent: {input_coords}", 'PurpleAir Downloader')

        # if the user wants to enter coordinates of the bounding box manually
        elif self.use_bb_coords_rb.isChecked():
            input_coords = (
                self.west_long_le.text(), self.east_long_le.text(), self.north_lat_le.text(), self.south_lat_le.text())
            # validating the coordinates via a helper function
            if not validate_input_coordinates(*input_coords):
                QtWidgets.QMessageBox.critical(None, "Validation error",
                                               "Bounding box coordinates you've entered appear to be invalid")
                return None
            else:
                QgsMessageLog.logMessage(f"user asked to enter coords manually, {input_coords}", 'PurpleAir Downloader')

        # if the user wants to download files within the extent of the particular layer
        elif self.use_le_rb.isChecked():
            if not QgsProject.instance().mapLayers().values():
                QtWidgets.QMessageBox.critical(None, "No layers",
                                               "Please check if you have layers added to a project. Can't get current "
                                               "extent.")
                return None
            else:
                # get the extent of the layer, selected from the drop-down menu
                layer_index = self.layers_combobox.currentIndex()
                try:
                    input_coords = get_layer_extent_by_index(layer_index)
                    QgsMessageLog.logMessage(f"user asked to use extent of the layer: {input_coords}", 'PurpleAir '
                                                                                                       'Downloader')
                except Exception as e:
                    QtWidgets.QMessageBox.critical(None, "Error occurred",
                                                   f"Can't get extent of the specified layer. Try to refresh list of"
                                                   f" the layers and try again.Error message {e}" )
                    return None

        # if all the validation steps passed, create dictionary to pass the parameters to PurpleAir API
        input_params = {
            'extent': input_coords,
            'start_date': start_date,
            'end_date': end_date,
            'sensor_type': sensor_type
        }

        QgsMessageLog.logMessage(f"{input_coords}, {start_date}, {end_date}, {sensor_type}", 'PurpleAir Downloader')

        try:
            jobs = get_sensor_list(input_params)
        except Exception as e:
            QtWidgets.QMessageBox.critical(None, "Failed to retrieve list of sensors",
                                           f"Failed to retrieve list of sensors. {e}")
            return None

        # checking if there are non-zero number of sensors in the current extent and warning the user
        if len(jobs) == 0:
            QtWidgets.QMessageBox.critical(None, "Nothing to download",
                                           "There are no sensors in the current extent. Please check another extent")
            return None

        # display the number of sensors to download and asking if the user wants to proceed
        reply = QtWidgets.QMessageBox.question(None, 'Do you want to proceed',
                                                     f"There are {len(jobs)} sensors to download. Would you like to continue?",
                                           QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.No:
            return None

        """
        creating a child QT thread to do avoid freezing the GUI while waiting for download to complete
        Ideas about progress bar implementation in PyQT borrowed from here: https://pythonpyqt.com/pyqt-progressbar/
        """
        self.thread = Thread(jobs=jobs)
        # here we connect the signal coming from the child thread to the function from the parend thread to
        # updated the progress bar
        self.thread.signal.connect(self.signal_accept)
        self.thread.start()
        # disabling the Download button and enabling a Cancel button when thread starts
        self.download_pb.setEnabled(False)
        self.stop_pb.setEnabled(True)

    def signal_accept(self, msg):
        """
        This method receives signal from the long running child thread and updates the progress bar
        """
        self.progressBar.setValue(int(msg))
        # if progressbar has reached 100%, reset it and enable/disable the appropriate buttons
        # one can add message box reporting successful completion as well.
        if self.progressBar.value() == 100:
            self.progressBar.setValue(0)
            self.download_pb.setEnabled(True)
            self.stop_pb.setEnabled(False)


    def stop_download(self):
        """
        This method is called when Cancel button is requested. It sets the instance variable stop_download = True
        which is detected inside of the loop in the run function, and unfinished futures get cancelled
        don't use terminate() - it looks it causes dirty shutdown of the QThread, and child threads
        run with concurrent futures will be never cancelled and continue to run.
        """
        self.thread.stop_download = True
        # self.thread.terminate()


    def refresh_layer_list(self):
        """
        this method updates list of the layers when Refresh button was clicked. The tool does not refresh the layers
        automatically, but it is possible by watching for specific QGis signals
        """
        names = [layer.name() for layer in QgsProject.instance().mapLayers().values()]
        self.layers_combobox.clear()
        self.layers_combobox.addItems(names)
