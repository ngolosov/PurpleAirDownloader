""" This file contains the GUI logic for the Settings form. It was partially created by Plugin Creator"""
import os
from qgis.PyQt import QtWidgets
from qgis.PyQt import uic

from .pa_downloader_heplers import write_settings, check_api_key

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'pa_downloader_dialog_settings.ui'))


class PurpleAirDownloaderDialogSettings(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(PurpleAirDownloaderDialogSettings, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.buttonBox.accepted.connect(self.accept)

    def accept(self):
        """ handle writing to json settings file here"""
        settings = {
            "api_key": self.pa_api_key_le.text(),
            "proc_num": self.proc_num_sb.text()
        }
        # if the user presses OK button, check if the API key is valid
        if check_api_key(settings['api_key']):
            write_settings(settings)
            self.reject()
        else:
            QtWidgets.QMessageBox.critical(None, "Invalid API key",
                                           "The API key you've entered did not pass validation at api.purpleair.com. "
                                           "Please contact their technical support")
