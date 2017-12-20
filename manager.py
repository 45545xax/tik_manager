import pymel.core as pm
import json
import os, fnmatch
from shutil import copyfile
import maya.mel as mel

#### Import for UI
import Qt
from Qt import QtWidgets, QtCore, QtGui
from maya import OpenMayaUI as omui

if Qt.__binding__ == "PySide":
    from shiboken import wrapInstance
    from Qt.QtCore import Signal
elif Qt.__binding__.startswith('PyQt'):
    from sip import wrapinstance as wrapInstance
    from Qt.Core import pyqtSignal as Signal
else:
    from shiboken2 import wrapInstance
    from Qt.QtCore import Signal

def getMayaMainWindow():
    """
    Gets the memory adress of the main window to connect Qt dialog to it.
    Returns:
        (long) Memory Adress
    """
    win = omui.MQtUtil_mainWindow()
    ptr = wrapInstance(long(win), QtWidgets.QMainWindow)
    return ptr

class TikManager(dict):
    def __init__(self):
        super(TikManager, self).__init__()
        self.currentProject = pm.workspace(q=1, rd=1)
        self.validCategories = ["Model", "Animation", "Rig", "Shading", "Render", "Other"]
        self.padding = 3

    def dumpJson(self, data,file):
        with open(file, "w") as f:
            json.dump(data, f, indent=4)


    def loadJson(self, file):
        if os.path.isfile(file):
            with open(file, 'r') as f:
                # The JSON module will read our file, and convert it to a python dictionary
                data = json.load(f)
                return data
        else:
            return None


    def folderCheck(self, folder):
        if not os.path.isdir(folder):
            os.makedirs(folder)

    def saveNewScene(self, category, userName, shotName, *args, **kwargs):
        """
        Saves the scene with formatted name and creates a json file for the scene
        Args:
            category: (String) Category if the scene. Valid categories are 'Model', 'Animation', 'Rig', 'Shading', 'Other'
            userName: (String) Predefined user who initiates the process
            shotName: (String) Base name of the scene. Eg. 'Shot01', 'CharacterA', 'BookRig' etc...
            *args: 
            **kwargs: 

        Returns: None

        """
        ## TODO // make sure for the unique naming
        projectPath = pm.workspace(q=1, rd=1)
        dataPath = os.path.normpath(os.path.join(projectPath, "data"))
        self.folderCheck(dataPath)
        jsonPath = os.path.normpath(os.path.join(dataPath, "json"))
        self.folderCheck(jsonPath)
        jsonCategoryPath = os.path.normpath(os.path.join(jsonPath, category))
        self.folderCheck(jsonCategoryPath)
        scenesPath = os.path.normpath(os.path.join(projectPath, "scenes"))
        self.folderCheck(scenesPath)
        categoryPath = os.path.normpath(os.path.join(scenesPath, category))
        self.folderCheck(category)
        shotPath = os.path.normpath(os.path.join(categoryPath, shotName))
        self.folderCheck(shotPath)

        jsonFile = os.path.join(jsonCategoryPath, "{}.json".format(shotName))

        version=1
        sceneName = "{0}_{1}_{2}_v{3}".format(shotName, category, userName, str(version).zfill(self.padding))
        sceneFile = os.path.join(shotPath, "{0}.mb".format(sceneName))
        pm.saveAs(sceneFile)

        referenceName = "{0}_{1}_forReference".format(shotName, category)
        referenceFile = os.path.join(shotPath, "{0}.mb".format(referenceName))
        copyfile(sceneFile, referenceFile)

        jsonInfo = {}
        jsonInfo["Name"]=shotName
        jsonInfo["Path"]=shotPath
        jsonInfo["Category"]=category
        jsonInfo["Creator"]=userName
        # jsonInfo["CurrentVersion"]=001
        # jsonInfo["LastVersion"] = version
        jsonInfo["ReferenceFile"]=referenceFile
        jsonInfo["ReferencedVersion"]=version
        jsonInfo["Versions"]=[[sceneFile, "Initial Save", userName]]
        self.dumpJson(jsonInfo, jsonFile)
        print "New Scene Saved as %s" %sceneName

    def saveVersion(self, userName, makeReference=True, versionNotes="", *args, **kwargs):
        """
        Saves a version for the predefined scene. The scene json file must be present at the /data/[Category] folder.
        Args:
            userName: (String) Predefined user who initiates the process
            makeReference: (Boolean) If set True, make a copy of the forReference file. There can be only one 'forReference' file for each scene
            versionNotes: (String) This string will be hold in the json file as well. Notes about the changes in the version.
            *args: 
            **kwargs: 

        Returns: None

        """

        projectPath = pm.workspace(q=1, rd=1)
        dataPath = os.path.normpath(os.path.join(projectPath, "data"))
        self.folderCheck(dataPath)
        jsonPath = os.path.normpath(os.path.join(dataPath, "json"))
        self.folderCheck(jsonPath)


        ## get the category from the folder
        # first get the parent dir
        shotDirectory = os.path.abspath(os.path.join(pm.sceneName(), os.pardir))
        shotName = os.path.basename(shotDirectory)
        # get the category directory
        categoryDir = os.path.abspath(os.path.join(shotDirectory, os.pardir))
        category = os.path.basename(categoryDir)

        jsonCategoryPath = os.path.normpath(os.path.join(jsonPath, category))
        self.folderCheck(jsonCategoryPath)

        # print shotName, category
        jsonFile = os.path.join(jsonCategoryPath, "{}.json".format(shotName))
        if os.path.isfile(jsonFile):
            jsonInfo = self.loadJson(jsonFile)


            currentVersion = len(jsonInfo["Versions"])+1
            # jsonInfo["LastVersion"] = jsonInfo["LastVersion"] + 1
            sceneName = "{0}_{1}_{2}_v{3}".format(jsonInfo["Name"], jsonInfo["Category"], userName, str(currentVersion).zfill(self.padding))
            sceneFile = os.path.join(jsonInfo["Path"], "{0}.mb".format(sceneName))
            pm.saveAs(sceneFile)
            jsonInfo["Versions"].append([sceneFile, versionNotes, userName])

            if makeReference:
                referenceName = "{0}_{1}_forReference".format(shotName, category)
                referenceFile = os.path.join(jsonInfo["Path"], "{0}.mb".format(referenceName))
                copyfile(sceneFile, referenceFile)
                jsonInfo["ReferenceFile"] = referenceFile
                jsonInfo["ReferencedVersion"] = currentVersion
            self.dumpJson(jsonInfo, jsonFile)

    def scanScenes(self, category):
        """
        Scans the folder for json files. Instead of scanning all of the json files at once, It will scan only the target category to speed up the process.
        Args:
            category: (String) This is the category which will be scanned

        Returns: List of all json files in the category

        """
        projectPath = pm.workspace(q=1, rd=1)
        dataPath = os.path.normpath(os.path.join(projectPath, "data"))
        self.folderCheck(dataPath)
        jsonPath = os.path.normpath(os.path.join(dataPath, "json"))
        self.folderCheck(jsonPath)
        jsonCategoryPath = os.path.normpath(os.path.join(jsonPath, category))
        self.folderCheck(jsonCategoryPath)

        allJsonFiles = []
        # niceNames = []
        for file in os.listdir(jsonCategoryPath):
            file=os.path.join(jsonCategoryPath, file)
            allJsonFiles.append(file)
        return allJsonFiles

    def loadScene(self, jsonFile, version=None, force=False):
        """
        Opens the scene with the related json file and given version.
        Args:
            jsonFile: (String) This is the path of the json file which holds the scene properties.
            version: (integer) The version specified in this flag will be loaded. If not specified, last saved version will be used. Default=None
            force: (Boolean) If True, it forces the scene to load LOSING ALL THE UNSAVED CHANGES in the current scene. Default is 'False' 

        Returns: None

        """
        ## TODO // Check for the target path exists
        jsonInfo = self.loadJson(jsonFile)
        print jsonInfo["Versions"]
        if not version:
            # print jsonInfo["Versions"]
            sceneFile = jsonInfo["Versions"][-1][0] ## this is the absolute scene path of the last saved version
        else:
            sceneFile = jsonInfo["Versions"][version-1][0] ## this is the absolute scene path of the specified version

        pm.openFile(sceneFile, prompt=False, force=force)

    def makeReference(self, jsonFile, version):
        """
        Makes the given version valid reference file. Basically it copies that file and names it as <Shot Name>_forReference.mb.
        There can be only one reference file for one scene. If there is another reference file it will be written on. Since Reference files
        are duplicates of a version in the folder, it is safe to do that.
        Args:
            jsonFile: (String) Path to the json file which holds the information about the scene
            version: (Integer) Version number of the scene which will be copied as reference file.

        Returns: None

        """

        jsonInfo = self.loadJson(jsonFile)
        sceneFile = jsonInfo["Versions"][version][0]
        referenceName = "{0}_{1}_forReference".format(jsonInfo["Name"], jsonInfo["Category"])
        referenceFile = os.path.join(jsonInfo["Path"]), "{0}.mb".format(referenceName)
        copyfile(sceneFile, referenceFile)
        jsonInfo["ReferenceFile"] = referenceFile
        jsonInfo["ReferencedVersion"] = version
        self.dumpJson(jsonInfo, jsonFile)

    def loadReference(self, jsonFile):
        jsonInfo = self.loadJson(jsonFile)
        referenceFile = jsonInfo["ReferenceFile"]
        if referenceFile:
            pm.FileReference(referenceFile)
        else:
            pm.warning("There is no reference set for this scene. Nothing changed")


    # def pathOps(self, fullPath, mode):
    #     """
    #     performs basic path operations.
    #     Args:
    #         fullPath: (Unicode) Absolute Path
    #         mode: (String) Valid modes are 'path', 'basename', 'filename', 'extension', 'drive'
    #
    #     Returns:
    #         Unicode
    #
    #     """
    #
    #     if mode == "drive":
    #         drive = os.path.splitdrive(fullPath)
    #         return drive
    #
    #     path, basename = os.path.split(fullPath)
    #     if mode == "path":
    #         return path
    #     if mode == "basename":
    #         return basename
    #     filename, ext = os.path.splitext(basename)
    #     if mode == "filename":
    #         return filename
    #     if mode == "extension":
    #         return ext


class MainUI(QtWidgets.QMainWindow):
    def __init__(self):
        for entry in QtWidgets.QApplication.allWidgets():
            if entry.objectName() == "SceneManager":
                entry.close()
        parent = getMayaMainWindow()
        super(MainUI, self).__init__(parent=parent)

        self.manager = TikManager()

        self.setObjectName(("MainWindow"))
        self.resize(680, 600)
        self.setMaximumSize(QtCore.QSize(680, 600))
        self.setWindowTitle(("Scene Manager"))
        self.setToolTip((""))
        self.setStatusTip((""))
        self.setWhatsThis((""))
        self.setAccessibleName((""))
        self.setAccessibleDescription((""))

        self.centralwidget = QtWidgets.QWidget(self)
        self.centralwidget.setObjectName(("centralwidget"))

        self.projectPath_label = QtWidgets.QLabel(self.centralwidget)
        self.projectPath_label.setGeometry(QtCore.QRect(30, 30, 51, 21))
        self.projectPath_label.setToolTip((""))
        self.projectPath_label.setStatusTip((""))
        self.projectPath_label.setWhatsThis((""))
        self.projectPath_label.setAccessibleName((""))
        self.projectPath_label.setAccessibleDescription((""))
        self.projectPath_label.setFrameShape(QtWidgets.QFrame.Box)
        self.projectPath_label.setLineWidth(1)
        self.projectPath_label.setText(("Project:"))
        self.projectPath_label.setTextFormat(QtCore.Qt.AutoText)
        self.projectPath_label.setScaledContents(False)
        self.projectPath_label.setObjectName(("projectPath_label"))

        self.projectPath_lineEdit = QtWidgets.QLineEdit(self.centralwidget)
        self.projectPath_lineEdit.setGeometry(QtCore.QRect(90, 30, 471, 21))
        self.projectPath_lineEdit.setToolTip((""))
        self.projectPath_lineEdit.setStatusTip((""))
        self.projectPath_lineEdit.setWhatsThis((""))
        self.projectPath_lineEdit.setAccessibleName((""))
        self.projectPath_lineEdit.setAccessibleDescription((""))
        self.projectPath_lineEdit.setText((self.manager.currentProject))
        self.projectPath_lineEdit.setReadOnly(True)
        self.projectPath_lineEdit.setObjectName(("projectPath_lineEdit"))

        self.setProject_pushButton = QtWidgets.QPushButton(self.centralwidget)
        self.setProject_pushButton.setGeometry(QtCore.QRect(580, 30, 75, 23))
        self.setProject_pushButton.setToolTip((""))
        self.setProject_pushButton.setStatusTip((""))
        self.setProject_pushButton.setWhatsThis((""))
        self.setProject_pushButton.setAccessibleName((""))
        self.setProject_pushButton.setAccessibleDescription((""))
        self.setProject_pushButton.setText(("SET"))
        self.setProject_pushButton.setObjectName(("setProject_pushButton"))
        
        self.category_tabWidget = QtWidgets.QTabWidget(self.centralwidget)
        self.category_tabWidget.setGeometry(QtCore.QRect(30, 110, 621, 21))
        self.category_tabWidget.setToolTip((""))
        self.category_tabWidget.setStatusTip((""))
        self.category_tabWidget.setWhatsThis((""))
        self.category_tabWidget.setAccessibleName((""))
        self.category_tabWidget.setAccessibleDescription((""))
        self.category_tabWidget.setDocumentMode(True)
        self.category_tabWidget.setObjectName(("category_tabWidget"))
        
        self.model_tab = QtWidgets.QWidget()
        self.model_tab.setObjectName(("model_tab"))
        self.category_tabWidget.addTab(self.model_tab, ("Model"))
        self.shading_tab = QtWidgets.QWidget()
        self.shading_tab.setObjectName(("shading_tab"))
        self.category_tabWidget.addTab(self.shading_tab, ("Shading"))
        self.rig_tab = QtWidgets.QWidget()
        self.rig_tab.setObjectName(("rig_tab"))
        self.category_tabWidget.addTab(self.rig_tab, ("Rig"))
        self.animation_tab = QtWidgets.QWidget()
        self.animation_tab.setObjectName(("animation_tab"))
        self.category_tabWidget.addTab(self.animation_tab, ("Animation"))
        self.render_tab = QtWidgets.QWidget()
        self.render_tab.setObjectName(("render_tab"))
        self.category_tabWidget.addTab(self.render_tab, ("Render"))
        self.other_tab = QtWidgets.QWidget()
        self.other_tab.setObjectName(("other_tab"))
        self.category_tabWidget.addTab(self.other_tab, ("Other"))

        self.loadMode_radioButton = QtWidgets.QRadioButton(self.centralwidget)
        self.loadMode_radioButton.setGeometry(QtCore.QRect(30, 67, 82, 31))
        self.loadMode_radioButton.setToolTip((""))
        self.loadMode_radioButton.setStatusTip((""))
        self.loadMode_radioButton.setWhatsThis((""))
        self.loadMode_radioButton.setAccessibleName((""))
        self.loadMode_radioButton.setAccessibleDescription((""))
        self.loadMode_radioButton.setText(("Load Mode"))
        self.loadMode_radioButton.setChecked(True)
        self.loadMode_radioButton.setObjectName(("loadMode_radioButton"))

        self.referenceMode_radioButton = QtWidgets.QRadioButton(self.centralwidget)
        self.referenceMode_radioButton.setGeometry(QtCore.QRect(130, 67, 101, 31))
        self.referenceMode_radioButton.setToolTip((""))
        self.referenceMode_radioButton.setStatusTip((""))
        self.referenceMode_radioButton.setWhatsThis((""))
        self.referenceMode_radioButton.setAccessibleName((""))
        self.referenceMode_radioButton.setAccessibleDescription((""))
        self.referenceMode_radioButton.setText(("Reference Mode"))
        self.referenceMode_radioButton.setObjectName(("referenceMode_radioButton"))

        self.userName_comboBox = QtWidgets.QComboBox(self.centralwidget)
        self.userName_comboBox.setGeometry(QtCore.QRect(553, 70, 101, 31))
        self.userName_comboBox.setToolTip((""))
        self.userName_comboBox.setStatusTip((""))
        self.userName_comboBox.setWhatsThis((""))
        self.userName_comboBox.setAccessibleName((""))
        self.userName_comboBox.setAccessibleDescription((""))
        self.userName_comboBox.setObjectName(("userName_comboBox"))
        self.userName_comboBox.addItem((""))
        self.userName_comboBox.setItemText(0, ("Arda Kutlu"))
        self.userName_comboBox.addItem((""))
        self.userName_comboBox.setItemText(1, ("Ilhan Yilmaz"))
        self.userName_comboBox.addItem((""))
        self.userName_comboBox.setItemText(2, ("Sinan Iren"))
        self.userName_comboBox.addItem((""))
        self.userName_comboBox.setItemText(3, ("Cihan Cicekel"))
        self.userName_comboBox.addItem((""))
        self.userName_comboBox.setItemText(4, ("Emir Karasakal"))
        self.userName_comboBox.addItem((""))
        self.userName_comboBox.setItemText(5, ("Orcun Ozdemir"))

        self.userName_label = QtWidgets.QLabel(self.centralwidget)
        self.userName_label.setGeometry(QtCore.QRect(520, 70, 31, 31))
        self.userName_label.setToolTip((""))
        self.userName_label.setStatusTip((""))
        self.userName_label.setWhatsThis((""))
        self.userName_label.setAccessibleName((""))
        self.userName_label.setAccessibleDescription((""))
        self.userName_label.setText(("User:"))
        self.userName_label.setObjectName(("userName_label"))

        self.scenes_listWidget = QtWidgets.QListWidget(self.centralwidget)
        self.scenes_listWidget.setGeometry(QtCore.QRect(30, 140, 381, 351))
        self.scenes_listWidget.setToolTip((""))
        self.scenes_listWidget.setStatusTip((""))
        self.scenes_listWidget.setWhatsThis((""))
        self.scenes_listWidget.setAccessibleName((""))
        self.scenes_listWidget.setAccessibleDescription((""))
        self.scenes_listWidget.setObjectName(("scenes_listWidget"))

        self.notes_textEdit = QtWidgets.QTextEdit(self.centralwidget)
        self.notes_textEdit.setGeometry(QtCore.QRect(430, 260, 221, 231))
        self.notes_textEdit.setToolTip((""))
        self.notes_textEdit.setStatusTip((""))
        self.notes_textEdit.setWhatsThis((""))
        self.notes_textEdit.setAccessibleName((""))
        self.notes_textEdit.setAccessibleDescription((""))
        self.notes_textEdit.setObjectName(("notes_textEdit"))

        self.version_comboBox = QtWidgets.QComboBox(self.centralwidget)
        self.version_comboBox.setGeometry(QtCore.QRect(490, 150, 71, 31))
        self.version_comboBox.setToolTip((""))
        self.version_comboBox.setStatusTip((""))
        self.version_comboBox.setWhatsThis((""))
        self.version_comboBox.setAccessibleName((""))
        self.version_comboBox.setAccessibleDescription((""))
        self.version_comboBox.setObjectName(("version_comboBox"))

        self.version_label = QtWidgets.QLabel(self.centralwidget)
        self.version_label.setGeometry(QtCore.QRect(430, 151, 51, 31))
        self.version_label.setToolTip((""))
        self.version_label.setStatusTip((""))
        self.version_label.setWhatsThis((""))
        self.version_label.setAccessibleName((""))
        self.version_label.setAccessibleDescription((""))
        self.version_label.setFrameShape(QtWidgets.QFrame.Box)
        self.version_label.setFrameShadow(QtWidgets.QFrame.Plain)
        self.version_label.setText(("Version:"))
        self.version_label.setObjectName(("version_label"))

        self.makeReference_pushButton = QtWidgets.QPushButton(self.centralwidget)
        self.makeReference_pushButton.setGeometry(QtCore.QRect(430, 200, 131, 23))
        self.makeReference_pushButton.setToolTip(("Creates a copy the scene as \'forReference\' file"))
        self.makeReference_pushButton.setStatusTip((""))
        self.makeReference_pushButton.setWhatsThis((""))
        self.makeReference_pushButton.setAccessibleName((""))
        self.makeReference_pushButton.setAccessibleDescription((""))
        self.makeReference_pushButton.setText(("Make Reference"))
        self.makeReference_pushButton.setShortcut((""))
        self.makeReference_pushButton.setObjectName(("makeReference_pushButton"))

        self.notes_label = QtWidgets.QLabel(self.centralwidget)
        self.notes_label.setGeometry(QtCore.QRect(430, 240, 46, 13))
        self.notes_label.setToolTip((""))
        self.notes_label.setStatusTip((""))
        self.notes_label.setWhatsThis((""))
        self.notes_label.setAccessibleName((""))
        self.notes_label.setAccessibleDescription((""))
        self.notes_label.setText(("NOTES"))
        self.notes_label.setObjectName(("notes_label"))

        self.saveScene_pushButton = QtWidgets.QPushButton(self.centralwidget)
        self.saveScene_pushButton.setGeometry(QtCore.QRect(40, 510, 151, 41))
        self.saveScene_pushButton.setToolTip(("Saves the Base Scene. This will save the scene and will make versioning possible."))
        self.saveScene_pushButton.setStatusTip((""))
        self.saveScene_pushButton.setWhatsThis((""))
        self.saveScene_pushButton.setAccessibleName((""))
        self.saveScene_pushButton.setAccessibleDescription((""))
        self.saveScene_pushButton.setText(("Save Base Scene"))
        self.saveScene_pushButton.setObjectName(("saveScene_pushButton"))

        self.saveAsVersion_pushButton = QtWidgets.QPushButton(self.centralwidget)
        self.saveAsVersion_pushButton.setGeometry(QtCore.QRect(210, 510, 151, 41))
        self.saveAsVersion_pushButton.setToolTip(("Saves the current scene as a version. A base scene must be present."))
        self.saveAsVersion_pushButton.setStatusTip((""))
        self.saveAsVersion_pushButton.setWhatsThis((""))
        self.saveAsVersion_pushButton.setAccessibleName((""))
        self.saveAsVersion_pushButton.setAccessibleDescription((""))
        self.saveAsVersion_pushButton.setText(("Save As Version"))
        self.saveAsVersion_pushButton.setObjectName(("saveAsVersion_pushButton"))

        self.load_pushButton = QtWidgets.QPushButton(self.centralwidget)
        self.load_pushButton.setGeometry(QtCore.QRect(500, 510, 151, 41))
        self.load_pushButton.setToolTip(("Loads the scene or Creates the selected reference depending on the mode"))
        self.load_pushButton.setStatusTip((""))
        self.load_pushButton.setWhatsThis((""))
        self.load_pushButton.setAccessibleName((""))
        self.load_pushButton.setAccessibleDescription((""))
        self.load_pushButton.setText(("Load Scene"))
        self.load_pushButton.setObjectName(("load_pushButton"))

        self.setCentralWidget(self.centralwidget)

        self.menubar = QtWidgets.QMenuBar(self)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 680, 18))
        self.menubar.setObjectName(("menubar"))
        self.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(self)
        self.statusbar.setObjectName(("statusbar"))
        self.setStatusBar(self.statusbar)
        self.setStatusBar(self.statusbar)

        self.loadMode_radioButton.toggled.connect(lambda: self.version_comboBox.setEnabled(self.loadMode_radioButton.isChecked()))
        self.loadMode_radioButton.toggled.connect(lambda: self.version_label.setEnabled(self.loadMode_radioButton.isChecked()))
        self.loadMode_radioButton.toggled.connect(lambda: self.makeReference_pushButton.setEnabled(self.loadMode_radioButton.isChecked()))
        self.loadMode_radioButton.toggled.connect(lambda: self.notes_label.setEnabled(self.loadMode_radioButton.isChecked()))
        self.loadMode_radioButton.toggled.connect(lambda: self.notes_textEdit.setEnabled(self.loadMode_radioButton.isChecked()))

        self.loadMode_radioButton.toggled.connect(lambda: self.load_pushButton.setText("Load Scene"))
        self.referenceMode_radioButton.toggled.connect(lambda: self.load_pushButton.setText("Reference Scene"))

        self.setProject_pushButton.clicked.connect(lambda: mel.eval("SetProject;"))

    def setProject(self):
        mel.eval("SetProject;")
        self.manager.currentProject = pm.workspace(q=1, rd=1)
        ## TODO INIT AGAIN

