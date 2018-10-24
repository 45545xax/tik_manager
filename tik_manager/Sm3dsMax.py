import os
import sys
# import ctypes
import SmRoot
reload(SmRoot)
from SmRoot import RootManager

import _version
import shutil

import datetime
import socket
import pprint
import logging


from PySide import QtGui
from PySide import QtCore

import MaxPlus

from MaxPlus import FileManager as fManager
from MaxPlus import PathManager as pManager


from pymxs import runtime as rt


__author__ = "Arda Kutlu"
__copyright__ = "Copyright 2018, Scene Manager for 3dsMax Projects"
__credits__ = []
__version__ = "2.0.0"
__license__ = "GPL"
__maintainer__ = "Arda Kutlu"
__email__ = "ardakutlu@gmail.com"
__status__ = "Development"

SM_Version = "Scene Manager 3ds Max v%s" %_version.__version__

logging.basicConfig()
logger = logging.getLogger('sm3dsMax')
logger.setLevel(logging.WARNING)

def excepthook(excType, excValue, tracebackobj):
    """Overrides sys.excepthook for gui feedback"""

    errorCodeDict = {200: "Corrupted File",
                     201: "Missing File",
                     202: "Read/Write Error",
                     203: "Delete Error",
                     210: "OS Not Supported",
                     101: "Out of range",
                     102: "Missing Override",
                     340: "Naming Error",
                     341: "Mandatory fields are not filled",
                     360: "Action not permitted"}


    errorCode = excValue[0][0]
    errorMsg = excValue[0][1]

    if errorCode == 200: # question box for this
        q = QtGui.QMessageBox()
        q.setStandardButtons(QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
        q.setText(errorMsg)
        q.setWindowTitle(errorCodeDict[errorCode])
        ret = q.exec_()
        if ret == QtGui.QMessageBox.Yes:
            os.startfile(excValue[0][2])
        elif ret == QtGui.QMessageBox.No:
            pass
            # print "no"

    else:
        errorbox = QtGui.QMessageBox()
        errorbox.setText(errorMsg)
        errorbox.setWindowTitle(errorCodeDict[errorCode])
        errorbox.exec_()

sys.excepthook = excepthook


class MaxManager(RootManager):
    def __init__(self):
        super(MaxManager, self).__init__()

        self.init_paths()
        # self.backwardcompatibility()  # DO NOT RUN UNTIL RELEASE
        self.init_database()


    def getSoftwarePaths(self):
        """Overriden function"""
        # To tell the base class maya specific path names
        return {"niceName": "3dsMax",
                "databaseDir": "maxDB",
                "scenesDir": "scenes_3dsMax",
                "pbSettingsFile": "pbSettings_3dsMax.json",
                "categoriesFile": "categories3dsMax.json",
                "userSettingsDir": "Documents\\SceneManager\\3dsMax"} # this is just for 3ds max. expanduser"~" returns different in max

    def getProjectDir(self):
        """Overriden function"""
        # p_path = pManager.GetProjectFolderDir()
        # norm_p_path = os.path.normpath(p_path)
        projectsDict = self._loadProjects()


        if not projectsDict:
            norm_p_path = os.path.normpath(pManager.GetProjectFolderDir())
            projectsDict = {"3dsMaxProject": norm_p_path}
            self._saveProjects(projectsDict)
            return norm_p_path

        # get the project defined in the database file
        try:
            norm_p_path = projectsDict["3dsMaxProject"]
            return norm_p_path
        except KeyError:
            norm_p_path = os.path.normpath(pManager.GetProjectFolderDir())
            projectsDict = {"3dsMaxProject": norm_p_path}
            self._saveProjects(projectsDict)
            return norm_p_path


    def getSceneFile(self):
        """Overriden function"""
        # Gets the current scene path ("" if untitled)
        logger.debug("GETSCENEFILE")
        s_path = fManager.GetFileNameAndPath()
        norm_s_path = os.path.normpath(s_path)
        return norm_s_path

    def setProject(self, path):
        """Sets the project"""
        projectsDict = self._loadProjects()
        if not projectsDict:
            projectsDict = {"3dsMaxProject": path}
        else:
            projectsDict["3dsMaxProject"] = path
        self._saveProjects(projectsDict)
        self.projectDir = path

    # def saveCallback(self):
    #     """Callback function to update reference files when files saved regularly"""
    #     ## TODO // TEST IT
    #     # self._pathsDict["sceneFile"] = self.getSceneFile() # unnecessary
    #     openSceneInfo = self.getOpenSceneInfo()
    #     if openSceneInfo["jsonFile"]:
    #         jsonInfo = self._loadJson(openSceneInfo["jsonFile"])
    #         if jsonInfo["ReferenceFile"]:
    #             absRefFile = os.path.join(self._pathsDict["projectDir"], jsonInfo["ReferenceFile"])
    #             absBaseSceneVersion = os.path.join(self._pathsDict["projectDir"], jsonInfo["Versions"][int(jsonInfo["ReferencedVersion"]) - 1]["RelativePath"])
    #             # if the refererenced scene file is the saved file (saved or saved as)
    #             if self._pathsDict["sceneFile"] == absBaseSceneVersion:
    #                 # copy over the forReference file
    #                 try:
    #                     shutil.copyfile(self._pathsDict["sceneFile"], absRefFile)
    #                     print "Scene Manager Update:\nReference File Updated"
    #                 except:
    #                     pass


    def saveBaseScene(self, categoryName, baseName, subProjectIndex=0, makeReference=True, versionNotes="", sceneFormat="max", *args, **kwargs):
        """
        Saves the scene with formatted name and creates a json file for the scene
        Args:
            category: (String) Category if the scene. Valid categories are 'Model', 'Animation', 'Rig', 'Shading', 'Other'
            userName: (String) Predefined user who initiates the process
            baseName: (String) Base name of the scene. Eg. 'Shot01', 'CharacterA', 'BookRig' etc...
            subProject: (Integer) The scene will be saved under the sub-project according to the given integer value. The 'self.subProjectList' will be
                searched with that integer.
            makeReference: (Boolean) If set True, a copy of the scene will be saved as forReference
            versionNotes: (String) This string will be stored in the json file as version notes.
            *args:
            **kwargs:

        Returns: Scene DB Dictionary

        """
        # fullName = self.userList.keys()[self.userList.values().index(userName)]
        now = datetime.datetime.now().strftime("%d/%m/%Y-%H:%M")
        completeNote = "[%s] on %s\n%s\n" % (self.currentUser, now, versionNotes)

        # Check if the base name is unique
        scenesToCheck = self.scanBaseScenes(categoryAs = categoryName, subProjectAs = subProjectIndex)
        for key in scenesToCheck.keys():
            if baseName.lower() == key.lower():
                msg = ("Base Scene Name is not unique!")
                logger.warning(msg)
                return -1, msg


        projectPath = self.projectDir
        databaseDir = self._pathsDict["databaseDir"]
        scenesPath = self._pathsDict["scenesDir"]
        categoryPath = os.path.normpath(os.path.join(scenesPath, categoryName))
        self._folderCheck(categoryPath)

        ## if its going to be saved as a subproject
        if not subProjectIndex == 0:
            subProjectPath = os.path.normpath(os.path.join(categoryPath, self._subProjectsList[subProjectIndex]))
            self._folderCheck(subProjectPath)
            shotPath = os.path.normpath(os.path.join(subProjectPath, baseName))
            self._folderCheck(shotPath)


            jsonCategoryPath = os.path.normpath(os.path.join(databaseDir, categoryName))
            self._folderCheck(jsonCategoryPath)
            jsonCategorySubPath = os.path.normpath(os.path.join(jsonCategoryPath, self._subProjectsList[subProjectIndex]))
            self._folderCheck(jsonCategorySubPath)
            jsonFile = os.path.join(jsonCategorySubPath, "{}.json".format(baseName))


        else:
            shotPath = os.path.normpath(os.path.join(categoryPath, baseName))
            self._folderCheck(shotPath)


            jsonCategoryPath = os.path.normpath(os.path.join(databaseDir, categoryName))
            self._folderCheck(jsonCategoryPath)
            jsonFile = os.path.join(jsonCategoryPath, "{}.json".format(baseName))


        version = 1
        sceneName = "{0}_{1}_{2}_v{3}".format(baseName, categoryName, self._usersDict[self.currentUser], str(version).zfill(3))

        sceneFile = os.path.join(shotPath, "{0}.{1}".format(sceneName, sceneFormat))
        ## relativity update
        relSceneFile = os.path.relpath(sceneFile, start=projectPath)

        fManager.Save(sceneFile)

        thumbPath = self.createThumbnail(dbPath=jsonFile, versionInt=version)

        jsonInfo = {}

        if makeReference:
            referenceName = "{0}_{1}_forReference".format(baseName, categoryName)
            referenceFile = os.path.join(shotPath, "{0}.{1}".format(referenceName, sceneFormat))
            ## relativity update
            relReferenceFile = os.path.relpath(referenceFile, start=projectPath)
            shutil.copyfile(sceneFile, referenceFile)
            jsonInfo["ReferenceFile"] = relReferenceFile
            jsonInfo["ReferencedVersion"] = version
        else:
            jsonInfo["ReferenceFile"] = None
            jsonInfo["ReferencedVersion"] = None

        # version serialization:
        version, api, sdk = rt.maxversion()
        vInfo = [version, api, sdk]

        jsonInfo["ID"] = "Sm3dsMaxV02_sceneFile"
        # jsonInfo["3dsMaxVersion"] = os.path.basename(os.path.split(pManager.GetMaxSysRootDir())[0])
        jsonInfo["3dsMaxVersion"] = vInfo
        jsonInfo["Name"] = baseName
        jsonInfo["Path"] = os.path.relpath(shotPath, start=projectPath)
        jsonInfo["Category"] = categoryName
        jsonInfo["Creator"] = self.currentUser
        jsonInfo["CreatorHost"] = (socket.gethostname())
        # jsonInfo["Versions"] = [ # PATH => Notes => User Initials => Machine ID => Playblast => Thumbnail
        #     [relSceneFile, completeNote,  self._usersDict[self.currentUser], socket.gethostname(), {}, thumbPath]]
        jsonInfo["Versions"] = [ # PATH => Notes => User Initials => Machine ID => Playblast => Thumbnail
            {"RelativePath": relSceneFile,
             "Note": completeNote,
             "User": self._usersDict[self.currentUser],
             "Workstation": socket.gethostname(),
             "Preview": {},
             "Thumb": thumbPath,
             "Ranges": self._getTimelineRanges()
             }
        ]
        jsonInfo["SubProject"] = self._subProjectsList[subProjectIndex]
        self._dumpJson(jsonInfo, jsonFile)
        return jsonInfo

    def saveVersion(self, makeReference=True, versionNotes="", sceneFormat="max", *args, **kwargs):
        """
        Saves a version for the predefined scene. The scene json file must be present at the /data/[Category] folder.
        Args:
            userName: (String) Predefined user who initiates the process
            makeReference: (Boolean) If set True, make a copy of the forReference file. There can be only one 'forReference' file for each scene
            versionNotes: (String) This string will be hold in the json file as well. Notes about the changes in the version.
            *args:
            **kwargs:

        Returns: Scene DB Dictionary

        """

        now = datetime.datetime.now().strftime("%d/%m/%Y-%H:%M")
        completeNote = "[%s] on %s\n%s\n" % (self.currentUser, now, versionNotes)

        sceneName = self.getSceneFile()
        if not sceneName:
            msg = "This is not a base scene (Untitled)"
            logger.warning(msg)
            return -1, msg

        sceneInfo = self.getOpenSceneInfo()

        if sceneInfo: ## getCurrentJson returns None if the resolved json path is missing
            jsonFile = sceneInfo["jsonFile"]
            jsonInfo = self._loadJson(jsonFile)
            if jsonInfo == -1:
                msg = "Database file is corrupted"
                return -1, msg

            currentVersion = len(jsonInfo["Versions"]) + 1
            sceneName = "{0}_{1}_{2}_v{3}".format(jsonInfo["Name"], jsonInfo["Category"], self._usersDict[self.currentUser],
                                                  str(currentVersion).zfill(3))
            relSceneFile = os.path.join(jsonInfo["Path"], "{0}.{1}".format(sceneName, sceneFormat))

            sceneFile = os.path.join(sceneInfo["projectPath"], relSceneFile)

            # killTurtle()
            # TODO // cmds?
            fManager.Save(sceneFile)

            thumbPath = self.createThumbnail(dbPath=jsonFile, versionInt=currentVersion)

            jsonInfo["Versions"].append(
                {"RelativePath": relSceneFile,
                 "Note": completeNote,
                 "User": self._usersDict[self.currentUser],
                 "Workstation": socket.gethostname(),
                 "Preview": {},
                 "Thumb": thumbPath,
                 "Ranges": self._getTimelineRanges()
                 }
                )

            if makeReference:
                referenceName = "{0}_{1}_forReference".format(jsonInfo["Name"], jsonInfo["Category"])
                relReferenceFile = os.path.join(jsonInfo["Path"], "{0}.{1}".format(referenceName, sceneFormat))
                referenceFile = os.path.join(sceneInfo["projectPath"], relReferenceFile)

                shutil.copyfile(sceneFile, referenceFile)
                jsonInfo["ReferenceFile"] = relReferenceFile
                jsonInfo["ReferencedVersion"] = currentVersion
            self._dumpJson(jsonInfo, jsonFile)
        else:
            msg = "This is not a base scene (Json file cannot be found)"
            logger.warning(msg)
            return -1, msg
        return jsonInfo


    def createPreview(self, *args, **kwargs):
        """Creates a Playblast preview from currently open scene"""
        # rt = pymxs.runtime

        openSceneInfo = self.getOpenSceneInfo()
        if not openSceneInfo:
            msg = "This is not a base scene. Scene must be saved as a base scene before playblasting."
            # raise Exception([360, msg])
            self._exception(360, msg)
            return
            # logger.warning(msg)
            # return -1, msg

        # get view info
        viewportType = rt.viewport.getType()
        print "CVP", viewportType
        if str(viewportType) == "view_camera":
            currentCam = str(rt.getActiveCamera().name)
        else:
            currentCam = str(viewportType)

        validName = currentCam.replace("|", "__").replace(" ", "_")
        extension = "avi"

        # versionName = rt.getFilenameFile(rt.maxFileName) #
        versionName = rt.maxFilePath + rt.maxFileName # abs path of the filename with extension
        print "versionName", versionName
        relVersionName = os.path.relpath(versionName, start=openSceneInfo["projectPath"]) # relative path of filename with ext

        if not os.path.isdir(os.path.normpath(openSceneInfo["previewPath"])):
            os.makedirs(os.path.normpath(openSceneInfo["previewPath"]))
        playBlastFile = os.path.join(openSceneInfo["previewPath"], "{0}_{1}_PB.{2}".format(self._niceName(versionName), validName, extension))
        relPlayBlastFile = os.path.relpath(playBlastFile, start=openSceneInfo["projectPath"])

        if os.path.isfile(playBlastFile):
            try:
                os.remove(playBlastFile)
            except WindowsError:
                msg = "The file is open somewhere else"
                logger.warning(msg)
                return -1, msg

        jsonInfo = self._loadJson(openSceneInfo["jsonFile"])
        if jsonInfo == -1:
            msg = "Database file is corrupted"
            return -1, msg
        # returns 0,"" if everything is ok, -1,msg if error

        pbSettings = self._loadPBSettings()
        originalValues = {"width": rt.renderWidth,
                        "height": rt.renderHeight
                        }

        originalSelection = rt.execute("selection as array")



        # change the render settings temporarily
        rt.renderWidth = pbSettings["Resolution"][0]
        rt.renderHeight = pbSettings["Resolution"][1]

        if pbSettings["PolygonOnly"]:
            dspGeometry = True
            dspShapes = False
            dspLights = False
            dspCameras = False
            dspHelpers = False
            dspParticles = False
            dspBones = False
        else:
            dspGeometry = True
            dspShapes = True
            dspLights = True
            dspCameras = True
            dspHelpers = True
            dspParticles = True
            dspBones = True

        dspGrid = pbSettings["ShowGrid"]
        dspFrameNums = pbSettings["ShowFrameNumber"]
        percentSize = pbSettings["Percent"]

        if pbSettings["WireOnShaded"]:
            rndLevel = rt.execute("#litwireframe")
        else:
            rndLevel = rt.execute("#smoothhighlights")

        if pbSettings["ClearSelection"]:
            rt.clearSelection()


        # find the path of where the avi file be created
        # if rt.maxFilePath:
        #     previewname = rt.getFilenameFile(rt.maxFileName)
        # else:
        #     previewname = "Untitled"

        sourceClip = rt.GetDir(rt.execute("#preview")) + "\_scene.avi "

        # destination = os.path.join(rt.maxFilePath, previewname)

        print "sourceClip is: %s" % sourceClip

        print "test: %s" %os.path.isfile(sourceClip)

        if os.path.isfile(sourceClip):
            try:
                os.remove(sourceClip)
            except WindowsError:
                msg = "Cannot continue creating preview.\n Close '%s' and try again" %sourceClip
                logger.error(msg)
                return -1, msg

        rt.createPreview(percentSize=percentSize, dspGeometry=dspGeometry,
                         dspShapes=dspShapes, dspLights=dspLights,
                         dspCameras=dspCameras, dspHelpers=dspHelpers,
                         dspParticles=dspParticles, dspBones=dspBones,
                         dspGrid=dspGrid, dspFrameNums=dspFrameNums,
                         rndLevel=rndLevel)


        # return the render width and height to original:
        rt.renderWidth = originalValues["width"]
        rt.renderHeight = originalValues["height"]

        rt.select(originalSelection)

        shutil.copy(sourceClip, playBlastFile)

        ## find this version in the json data
        print "relVersionName", relVersionName
        print "jInfo", jsonInfo

        for version in jsonInfo["Versions"]:
            if relVersionName == version["RelativePath"]:
                version["Preview"][currentCam] = relPlayBlastFile

        self._dumpJson(jsonInfo, openSceneInfo["jsonFile"])
        return 0, ""


    def loadBaseScene(self, force=False):
        """Loads the scene at cursor position"""
        # TODO // TEST IT
        relSceneFile = self._currentSceneInfo["Versions"][self._currentVersionIndex-1]["RelativePath"]
        absSceneFile = os.path.join(self.projectDir, relSceneFile)
        if os.path.isfile(absSceneFile):
            fManager.Open(absSceneFile)
            # cmds.file(absSceneFile, o=True, force=force)
            return 0
        else:
            msg = "File in Scene Manager database doesnt exist"
            logger.error(msg)
            return -1, msg

    def importBaseScene(self):
        """Imports the scene at cursor position"""
        relSceneFile = self._currentSceneInfo["Versions"][self._currentVersionIndex-1]["RelativePath"]
        absSceneFile = os.path.join(self.projectDir, relSceneFile)
        if os.path.isfile(absSceneFile):
            fManager.Merge(absSceneFile, mergeAll=True, selectMerged=True)
            # cmds.file(absSceneFile, i=True)
            return 0
        else:
            msg = "File in Scene Manager database doesnt exist"
            logger.error(msg)
            return -1, msg

    def referenceBaseScene(self):
        """Creates reference from the scene at cursor position"""

        projectPath = self.projectDir
        relReferenceFile = self._currentSceneInfo["ReferenceFile"]


        if relReferenceFile:
            referenceFile = os.path.join(projectPath, relReferenceFile)

            # software specific
            Xrefobjs = rt.getMAXFileObjectNames(referenceFile)
            rt.xrefs.addNewXRefObject(referenceFile, Xrefobjs)
            try:
                ranges = self._currentSceneInfo["Versions"][self._currentSceneInfo["ReferencedVersion"]-1]["Ranges"]
                self._setTimelineRanges(ranges)
            except KeyError:
                pass

        else:
            logger.warning("There is no reference set for this scene. Nothing changed")


    def createThumbnail(self, useCursorPosition=False, dbPath = None, versionInt = None):
        """
        Creates the thumbnail file.
        :param databaseDir: (String) If defined, this folder will be used to store the created database.
        :param version: (integer) if defined this version number will be used instead currently open scene version.
        :return: (String) Relative path of the thumbnail file
        """
        projectPath = self.projectDir
        if useCursorPosition:
            versionInt = self.currentVersionIndex
            dbPath = self.currentDatabasePath
        else:
            if not dbPath or not versionInt:
                logger.warning (("Both dbPath and version must be defined if useCursorPosition=False"))

        versionStr = "v%s" % (str(versionInt).zfill(3))
        dbDir, shotNameWithExt = os.path.split(dbPath)
        shotName = os.path.splitext(shotNameWithExt)[0]

        thumbPath = "{0}_{1}_thumb.jpg".format(os.path.join(dbDir, shotName), versionStr)
        relThumbPath = os.path.relpath(thumbPath, projectPath)

        ## Software specific section
        # rt = pymxs.runtime
        oWidth = 221
        oHeight = 124

        grab = rt.gw.getViewportDib()

        ratio = float(grab.width)/float(grab.height)

        if ratio <= 1.782:
            new_width = oHeight * ratio
            new_height = oHeight
        else:
            new_width = oWidth
            new_height = oWidth / ratio

        resizeFrame = rt.bitmap(new_width, new_height, color = rt.color(0,0,0))
        rt.copy(grab, resizeFrame)
        thumbFrame = rt.bitmap(oWidth, oHeight, color = rt.color(0,0,0))
        xOffset = (oWidth - resizeFrame.width) /2
        yOffset = (oHeight - resizeFrame.height) /2

        rt.pasteBitmap(resizeFrame, thumbFrame, rt.point2(0, 0), rt.point2(xOffset, yOffset))

        # rt.display(thumbFrame)

        thumbFrame.filename = thumbPath
        rt.save(thumbFrame)
        rt.close(thumbFrame)



        # img = rt.gw.getViewportDib()
        # img.fileName = thumbPath
        # rt.save(img)
        # rt.close(img)

        return relThumbPath


    def replaceThumbnail(self, filePath=None ):
        """
        Replaces the thumbnail with given file or current view
        :param filePath: (String)  if a filePath is defined, this image (.jpg or .gif) will be used as thumbnail
        :return: None
        """
        if not filePath:
            filePath = self.createThumbnail(useCursorPosition=True)

        self._currentSceneInfo["Versions"][self.currentVersionIndex-1]["Thumb"]=filePath


        # try:
        #     self._currentSceneInfo["Versions"][self.currentVersionIndex-1][5]=filePath
        # except IndexError: # if this is an older file without thumbnail
        #     self._currentSceneInfo["Versions"][self.currentVersionIndex-1].append(filePath)

        self._dumpJson(self._currentSceneInfo, self.currentDatabasePath)

    def compareVersions(self):
        """Compares the versions of current session and database version at cursor position"""
        # TODO : Write compare function for 3ds max
        # return 0, ""
        if not self._currentSceneInfo["3dsMaxVersion"]:
            logger.warning("Cursor is not on a base scene")
            return
        versionDict = {11000: "v2009",
                       12000: "v2010",
                       13000: "v2011",
                       14000: "v2012",
                       15000: "v2013",
                       16000: "v2014",
                       17000: "v2015",
                       18000: "v2016",
                       19000: "v2017",
                       20000: "v2018"
                       }

        #version serialization:
        version, api, sdk = rt.maxversion()
        currentVersion = [version, api, sdk]
        logger.debug("currentversion %s" %currentVersion)
        baseSceneVersion = self._currentSceneInfo["3dsMaxVersion"]
        logger.debug("baseVersion %s" % baseSceneVersion)

        try:
            niceVName = versionDict[currentVersion[0]]
        except KeyError:
            niceVName = str(currentVersion[0])

        if currentVersion == baseSceneVersion:
            msg = ""
            return 0, msg

        if currentVersion[0] < baseSceneVersion[0]: # max version compare
            message = "Base Scene is created with a LOWER 3ds Max version ({0}). Are you sure you want to continue?".format(niceVName)
            return -1, message

        if currentVersion[0] > baseSceneVersion[0]:
            message = "Base Scene is created with a HIGHER 3ds Max version ({0}). Are you sure you want to continue?".format(niceVName)
            return -1, message

        if currentVersion[1] > baseSceneVersion[1]: # max Api
            message = "Base Scene is created with a LOWER Build ({0}). Are you sure you want to continue?".format(niceVName)
            return -1, message

        if currentVersion[1] > baseSceneVersion[1]:
            message = "Base Scene is created with a HIGHER Build ({0}). Are you sure you want to continue?".format(niceVName)
            return -1, message

        # old or corrupted database
        return 0, ""  # skip


    def isSceneModified(self):
        """Checks the currently open scene saved or not"""
        return fManager.IsSaveRequired()

    def saveSimple(self):
        """Save the currently open file"""
        fManager.Save()

    def getFormatsAndCodecs(self):
        """Returns the codecs which can be used in current workstation"""
        # TODO : Write Get Formats and Codecs for 3ds max (if applicable)
        logger.warning ("getFormatsAndCodecs Function not written yet")
        # formatList = cmds.playblast(query=True, format=True)
        # codecsDictionary = dict(
        #     (item, mel.eval('playblast -format "{0}" -q -compression;'.format(item))) for item in formatList)
        # return codecsDictionary

    def preSaveChecklist(self):
        """Checks the scene for inconsistencies"""
        checklist = []

        # TODO : Create a fps comparison with the settings file
        fpsValue_setting = self.getFPS()
        fpsValue_current = rt.framerate
        if fpsValue_setting is not fpsValue_current:
            msg = "FPS values are not matching with the project settings.\n Project FPS => {0}\n scene FPS => {1}\nDo you want to continue?".format(fpsValue_setting, fpsValue_current)
            checklist.append(msg)

        return checklist

    def _exception(self, code, msg):
        """Overriden Function"""

        rt.messageBox(msg, title=self.errorCodeDict[code])
        # logger.debug("Exception %s" %errorCodeDict[code])
        # logger.debug(msg)

    def _getTimelineRanges(self):
        R_ast = int(rt.animationRange.start)
        R_min = int(rt.animationRange.start)
        R_max = int(rt.animationRange.end)
        R_aet = int(rt.animationRange.end)
        return [R_ast, R_min, R_max, R_aet]

    def _setTimelineRanges(self, rangeList):
        """Sets the timeline ranges [AnimationStart, Min, Max, AnimationEnd]"""
        rt.animationRange = rt.interval(rangeList[0], rangeList[-1])

    rt.animationRange = rt.interval(4, 12)

    def _createCallbacks(self, handler):
        logger.warning("_createCallbacks Function not written yet")
        # callbackIDList=[]
        # callbackIDList.append(cmds.scriptJob(e=["workspaceChanged", "%s.initMainUI()" % handler], replacePrevious=True, parent=SM_Version))
        # return callbackIDList

    def _killCallbacks(self, callbackIDList):
        logger.warning("_killCallbacks Function not written yet")
        # for x in callbackIDList:
        #     if cmds.scriptJob(ex=x):
        #         cmds.scriptJob(kill=x)

class _GCProtector(object):
    widgets = []

# noinspection PyArgumentList
app = QtGui.QApplication.instance()
if not app:
    app = QtGui.QApplication([])


class MainUI(QtGui.QMainWindow):
    """Main UI Class for Tik Scene Manager"""
    def __init__(self, callback=None):
        self.isCallback = callback
        for entry in QtGui.QApplication.allWidgets():
            try:
                if entry.objectName() == SM_Version:
                    entry.close()
            except AttributeError:
                pass

        parent = QtGui.QWidget(MaxPlus.GetQMaxWindow())
        super(MainUI, self).__init__(parent=parent)
        # super(MainUI, self).__init__(parent=None)
        self.manager = MaxManager()
        problem, msg = self.manager._checkRequirements()
        if problem:
            q = QtGui.QMessageBox()
            q.setIcon(QtGui.QMessageBox.Information)
            q.setText(msg[0])
            q.setInformativeText(msg[1])
            q.setWindowTitle(msg[2])
            q.setStandardButtons(QtGui.QMessageBox.Ok)

            ret = q.exec_()
            if ret == QtGui.QMessageBox.Ok:
                self.close()
                self.deleteLater()

        self.setObjectName(SM_Version)
        self.resize(680, 600)
        self.setWindowTitle(SM_Version)

        self.centralwidget = QtGui.QWidget(self)
        self.centralwidget.setObjectName("centralwidget")

        # self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        self.buildUI()
        self.setCentralWidget(self.centralwidget)

        self.callbackIDList=[]
        if self.isCallback:
            self.callbackIDList = self.manager._createCallbacks(self.isCallback)

        self.initMainUI(newborn=True)

    # def closeEvent(self, event):
    #     self.manager._killCallbacks(self.callbackIDList)

        # super(MainUI, self).closeEvent(event)


    def buildUI(self):

        self.main_gridLayout = QtGui.QGridLayout(self.centralwidget)
        self.main_gridLayout.setObjectName(("main_gridLayout"))

        self.main_horizontalLayout = QtGui.QHBoxLayout()
        self.main_horizontalLayout.setContentsMargins(-1, -1, 0, -1)
        self.main_horizontalLayout.setSpacing(6)
        self.main_horizontalLayout.setObjectName(("horizontalLayout"))
        self.main_horizontalLayout.setStretch(0, 1)

        self.saveBaseScene_pushButton = QtGui.QPushButton(self.centralwidget)
        self.saveBaseScene_pushButton.setMinimumSize(QtCore.QSize(150, 45))
        self.saveBaseScene_pushButton.setMaximumSize(QtCore.QSize(150, 45))
        self.saveBaseScene_pushButton.setText(("Save Base Scene"))
        self.saveBaseScene_pushButton.setObjectName(("saveBaseScene_pushButton"))
        self.main_horizontalLayout.addWidget(self.saveBaseScene_pushButton)

        self.saveVersion_pushButton = QtGui.QPushButton(self.centralwidget)
        self.saveVersion_pushButton.setMinimumSize(QtCore.QSize(150, 45))
        self.saveVersion_pushButton.setMaximumSize(QtCore.QSize(150, 45))
        self.saveVersion_pushButton.setText(("Save As Version"))
        self.saveVersion_pushButton.setObjectName(("saveVersion_pushButton"))
        self.main_horizontalLayout.addWidget(self.saveVersion_pushButton)

        spacerItem = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.main_horizontalLayout.addItem(spacerItem)

        self.loadScene_pushButton = QtGui.QPushButton(self.centralwidget)
        self.loadScene_pushButton.setMinimumSize(QtCore.QSize(150, 45))
        self.loadScene_pushButton.setMaximumSize(QtCore.QSize(150, 45))
        self.loadScene_pushButton.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.loadScene_pushButton.setText(("Load Scene"))
        self.loadScene_pushButton.setObjectName(("loadScene_pushButton"))
        self.main_horizontalLayout.addWidget(self.loadScene_pushButton)
        #
        self.main_gridLayout.addLayout(self.main_horizontalLayout, 4, 0, 1, 1)
        #
        self.r2_gridLayout = QtGui.QGridLayout()
        self.r2_gridLayout.setObjectName(("r2_gridLayout"))
        self.r2_gridLayout.setColumnStretch(1, 1)

        self.load_radioButton = QtGui.QRadioButton(self.centralwidget)
        self.load_radioButton.setText(("Load Mode"))
        # self.load_radioButton.setChecked(False)
        self.load_radioButton.setObjectName(("load_radioButton"))
        # print self.manager.currentMode
        self.load_radioButton.setChecked(self.manager.currentMode)
        self.r2_gridLayout.addWidget(self.load_radioButton, 0, 0, 1, 1)


        self.subProject_label = QtGui.QLabel(self.centralwidget)
        self.subProject_label.setText(("Sub-Project:"))
        self.subProject_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing | QtCore.Qt.AlignVCenter)
        self.subProject_label.setObjectName(("subProject_label"))
        self.r2_gridLayout.addWidget(self.subProject_label, 0, 2, 1, 1)

        self.subProject_comboBox = QtGui.QComboBox(self.centralwidget)
        self.subProject_comboBox.setMinimumSize(QtCore.QSize(150, 30))
        self.subProject_comboBox.setMaximumSize(QtCore.QSize(16777215, 30))
        self.subProject_comboBox.setObjectName(("subProject_comboBox"))
        self.r2_gridLayout.addWidget(self.subProject_comboBox, 0, 3, 1, 1)

        self.reference_radioButton = QtGui.QRadioButton(self.centralwidget)
        self.reference_radioButton.setText(("Reference Mode"))
        self.reference_radioButton.setChecked(not self.manager.currentMode)
        self.reference_radioButton.setObjectName(("reference_radioButton"))
        self.r2_gridLayout.addWidget(self.reference_radioButton, 0, 1, 1, 1)

        self.addSubProject_pushButton = QtGui.QPushButton(self.centralwidget)
        self.addSubProject_pushButton.setMinimumSize(QtCore.QSize(30, 30))
        self.addSubProject_pushButton.setMaximumSize(QtCore.QSize(30, 30))
        self.addSubProject_pushButton.setText(("+"))
        self.addSubProject_pushButton.setObjectName(("addSubProject_pushButton"))
        self.r2_gridLayout.addWidget(self.addSubProject_pushButton, 0, 4, 1, 1)

        self.user_label = QtGui.QLabel(self.centralwidget)
        self.user_label.setText(("User:"))
        self.user_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing | QtCore.Qt.AlignVCenter)
        self.user_label.setObjectName(("user_label"))
        self.r2_gridLayout.addWidget(self.user_label, 0, 5, 1, 1)

        self.user_comboBox = QtGui.QComboBox(self.centralwidget)
        self.user_comboBox.setMinimumSize(QtCore.QSize(130, 30))
        self.user_comboBox.setMaximumSize(QtCore.QSize(16777215, 30))
        self.user_comboBox.setObjectName(("user_comboBox"))
        self.r2_gridLayout.addWidget(self.user_comboBox, 0, 6, 1, 1)

        self.main_gridLayout.addLayout(self.r2_gridLayout, 1, 0, 1, 1)
        self.r1_gridLayout = QtGui.QGridLayout()
        self.r1_gridLayout.setObjectName(("r1_gridLayout"))

        self.baseScene_label = QtGui.QLabel(self.centralwidget)
        self.baseScene_label.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.baseScene_label.setText(("Base Scene:"))
        self.baseScene_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing | QtCore.Qt.AlignVCenter)
        self.baseScene_label.setObjectName(("baseScene_label"))
        self.r1_gridLayout.addWidget(self.baseScene_label, 0, 0, 1, 1)

        self.baseScene_lineEdit = QtGui.QLineEdit(self.centralwidget)
        self.baseScene_lineEdit.setText((""))
        self.baseScene_lineEdit.setPlaceholderText((""))
        self.baseScene_lineEdit.setObjectName(("baseScene_lineEdit"))
        self.r1_gridLayout.addWidget(self.baseScene_lineEdit, 0, 1, 1, 1)

        self.project_label = QtGui.QLabel(self.centralwidget)
        self.project_label.setText(("Project:"))
        self.project_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing | QtCore.Qt.AlignVCenter)
        self.project_label.setObjectName(("project_label"))
        self.r1_gridLayout.addWidget(self.project_label, 1, 0, 1, 1)

        self.project_lineEdit = QtGui.QLineEdit(self.centralwidget)
        self.project_lineEdit.setText((""))
        self.project_lineEdit.setPlaceholderText((""))
        self.project_lineEdit.setObjectName(("project_lineEdit"))
        self.project_lineEdit.setReadOnly(True)
        self.r1_gridLayout.addWidget(self.project_lineEdit, 1, 1, 1, 1)

        self.setProject_pushButton = QtGui.QPushButton(self.centralwidget)
        self.setProject_pushButton.setText(("SET"))
        self.setProject_pushButton.setObjectName(("setProject_pushButton"))
        self.r1_gridLayout.addWidget(self.setProject_pushButton, 1, 2, 1, 1)

        self.main_gridLayout.addLayout(self.r1_gridLayout, 0, 0, 1, 1)

        self.category_tabWidget = QtGui.QTabWidget(self.centralwidget)
        self.category_tabWidget.setMaximumSize(QtCore.QSize(16777215, 20))
        self.category_tabWidget.setTabPosition(QtGui.QTabWidget.North)
        self.category_tabWidget.setElideMode(QtCore.Qt.ElideNone)
        self.category_tabWidget.setUsesScrollButtons(False)
        self.category_tabWidget.setObjectName(("tabWidget"))

        # for i in self.manager._categories:
        #     self.preTab = QtGui.QWidget()
        #     self.preTab.setObjectName((i))
        #     self.category_tabWidget.addTab(self.preTab, (i))

        self.category_tabWidget.setCurrentIndex(self.manager.currentTabIndex)

        self.main_gridLayout.addWidget(self.category_tabWidget, 2, 0, 1, 1)

        self.splitter = QtGui.QSplitter(self.centralwidget)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self.splitter.setObjectName(("splitter"))


        self.scenes_listWidget = QtGui.QListWidget(self.splitter)
        self.scenes_listWidget.setObjectName(("listWidget"))

        self.frame = QtGui.QFrame(self.splitter)
        self.frame.setFrameShape(QtGui.QFrame.StyledPanel)
        self.frame.setFrameShadow(QtGui.QFrame.Raised)
        self.frame.setObjectName(("frame"))

        self.gridLayout_6 = QtGui.QGridLayout(self.frame)
        self.gridLayout_6.setContentsMargins(-1, -1, 0, 0)
        self.gridLayout_6.setObjectName(("gridLayout_6"))

        self.verticalLayout = QtGui.QVBoxLayout()
        self.verticalLayout.setObjectName(("verticalLayout"))

        self.notes_label = QtGui.QLabel(self.frame)
        self.notes_label.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.notes_label.setText(("Version Notes:"))
        self.notes_label.setAlignment(QtCore.Qt.AlignLeading | QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.notes_label.setObjectName(("version_label_2"))
        self.verticalLayout.addWidget(self.notes_label)

        self.notes_textEdit = QtGui.QTextEdit(self.frame)
        self.notes_textEdit.setObjectName(("textEdit"))
        self.notes_textEdit.setReadOnly(True)
        self.verticalLayout.addWidget(self.notes_textEdit)

        self.tPixmap = QtGui.QPixmap("")
        self.thumbnail_label = ImageWidget(self.frame)
        self.thumbnail_label.setPixmap(self.tPixmap)

        self.thumbnail_label.setMinimumSize(QtCore.QSize(221, 124))
        self.thumbnail_label.setFrameShape(QtGui.QFrame.Box)
        self.thumbnail_label.setScaledContents(True)
        self.thumbnail_label.setAlignment(QtCore.Qt.AlignCenter)
        self.thumbnail_label.setObjectName(("label"))
        self.verticalLayout.addWidget(self.thumbnail_label)

        self.gridLayout_6.addLayout(self.verticalLayout, 3, 0, 1, 1)

        self.gridLayout_7 = QtGui.QGridLayout()
        self.gridLayout_7.setContentsMargins(-1, -1, 10, 10)
        self.gridLayout_7.setObjectName(("gridLayout_7"))

        self.showPreview_pushButton = QtGui.QPushButton(self.frame)
        self.showPreview_pushButton.setMinimumSize(QtCore.QSize(100, 30))
        self.showPreview_pushButton.setMaximumSize(QtCore.QSize(150, 30))
        self.showPreview_pushButton.setText(("Show Preview"))
        self.showPreview_pushButton.setObjectName(("setProject_pushButton_5"))
        self.gridLayout_7.addWidget(self.showPreview_pushButton, 0, 3, 1, 1)

        self.horizontalLayout_4 = QtGui.QHBoxLayout()
        self.horizontalLayout_4.setSpacing(1)
        self.horizontalLayout_4.setObjectName(("horizontalLayout_4"))

        self.version_label = QtGui.QLabel(self.frame)
        self.version_label.setMinimumSize(QtCore.QSize(60, 30))
        self.version_label.setMaximumSize(QtCore.QSize(60, 30))
        self.version_label.setFrameShape(QtGui.QFrame.Box)
        self.version_label.setText(("Version:"))
        self.version_label.setAlignment(QtCore.Qt.AlignCenter)
        self.version_label.setObjectName(("version_label"))
        self.horizontalLayout_4.addWidget(self.version_label)

        self.version_comboBox = QtGui.QComboBox(self.frame)
        self.version_comboBox.setMinimumSize(QtCore.QSize(60, 30))
        self.version_comboBox.setMaximumSize(QtCore.QSize(100, 30))
        self.version_comboBox.setObjectName(("version_comboBox"))
        self.horizontalLayout_4.addWidget(self.version_comboBox)

        self.gridLayout_7.addLayout(self.horizontalLayout_4, 0, 0, 1, 1)

        self.makeReference_pushButton = QtGui.QPushButton(self.frame)
        self.makeReference_pushButton.setMinimumSize(QtCore.QSize(100, 30))
        self.makeReference_pushButton.setMaximumSize(QtCore.QSize(300, 30))
        self.makeReference_pushButton.setText(("Make Reference"))
        self.makeReference_pushButton.setObjectName(("makeReference_pushButton"))
        self.gridLayout_7.addWidget(self.makeReference_pushButton, 1, 0, 1, 1)

        self.addNote_pushButton = QtGui.QPushButton(self.frame)
        self.addNote_pushButton.setMinimumSize(QtCore.QSize(100, 30))
        self.addNote_pushButton.setMaximumSize(QtCore.QSize(150, 30))
        self.addNote_pushButton.setToolTip((""))
        self.addNote_pushButton.setStatusTip((""))
        self.addNote_pushButton.setWhatsThis((""))
        self.addNote_pushButton.setAccessibleName((""))
        self.addNote_pushButton.setAccessibleDescription((""))
        self.addNote_pushButton.setText(("Add Note"))
        self.addNote_pushButton.setObjectName(("addNote_pushButton"))
        self.gridLayout_7.addWidget(self.addNote_pushButton, 1, 3, 1, 1)

        self.gridLayout_6.addLayout(self.gridLayout_7, 0, 0, 1, 1)

        self.main_gridLayout.addWidget(self.splitter, 3, 0, 1, 1)

        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(1)
        self.splitter.setSizePolicy(sizePolicy)

        self.splitter.setStretchFactor(0, 1)

        self.menubar = QtGui.QMenuBar(self)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 680, 18))
        self.menubar.setObjectName(("menubar"))

        self.setMenuBar(self.menubar)
        self.statusbar = QtGui.QStatusBar(self)
        self.statusbar.setObjectName(("statusbar"))
        self.setStatusBar(self.statusbar)

        # MENU BAR / STATUS BAR
        # ---------------------
        file = self.menubar.addMenu("File")
        saveVersion_fm = QtGui.QAction("&Save Version", self)
        saveBaseScene_fm = QtGui.QAction("&Save Base Scene", self)
        loadReferenceScene_fm = QtGui.QAction("&Load/Reference Scene", self)
        createProject_fm = QtGui.QAction("&Create Project", self)
        add_remove_users_fm = QtGui.QAction("&Add/Remove Users", self)
        add_remove_categories_fm = QtGui.QAction("&Add/Remove Categories", self)
        projectSettings_fm = QtGui.QAction("&Project Settings", self)

        pb_settings_fm = QtGui.QAction("&Playblast Settings", self)


        deleteFile_fm = QtGui.QAction("&Delete Selected Base Scene", self)
        deleteReference_fm = QtGui.QAction("&Delete Reference of Selected Scene", self)
        reBuildDatabase_fm = QtGui.QAction("&Re-build Project Database", self)
        projectReport_fm = QtGui.QAction("&Project Report", self)
        checkReferences_fm = QtGui.QAction("&Check References", self)

        #save
        file.addAction(createProject_fm)
        file.addAction(saveVersion_fm)
        file.addAction(saveBaseScene_fm)

        #load
        file.addSeparator()
        file.addAction(loadReferenceScene_fm)

        #settings
        file.addSeparator()
        file.addAction(add_remove_users_fm)
        file.addAction(add_remove_categories_fm)
        file.addAction(pb_settings_fm)
        file.addAction(projectSettings_fm)


        #delete
        file.addSeparator()
        file.addAction(deleteFile_fm)
        file.addAction(deleteReference_fm)

        #misc
        file.addSeparator()
        file.addAction(projectReport_fm)
        file.addAction(checkReferences_fm)

        tools = self.menubar.addMenu("Tools")
        imanager = QtGui.QAction("&Image Manager", self)
        iviewer = QtGui.QAction("&Image Viewer", self)
        createPB = QtGui.QAction("&Create PlayBlast", self)

        tools.addAction(imanager)
        tools.addAction(iviewer)
        tools.addAction(createPB)

        # RIGHT CLICK MENUS
        # -----------------

        # List Widget Right Click Menu
        self.scenes_listWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.scenes_listWidget.customContextMenuRequested.connect(self.onContextMenu_scenes)
        self.popMenu_scenes = QtGui.QMenu()

        self.scenes_rcItem_0 = QtGui.QAction('Import Scene', self)
        self.popMenu_scenes.addAction(self.scenes_rcItem_0)
        self.scenes_rcItem_0.triggered.connect(lambda: self.rcAction_scenes("importScene"))

        self.scenes_rcItem_1 = QtGui.QAction('Show 3dsMax Folder in Explorer', self)
        self.popMenu_scenes.addAction(self.scenes_rcItem_1)
        self.scenes_rcItem_1.triggered.connect(lambda: self.rcAction_scenes("showInExplorerMaya"))

        self.scenes_rcItem_2 = QtGui.QAction('Show Playblast Folder in Explorer', self)
        self.popMenu_scenes.addAction(self.scenes_rcItem_2)
        self.scenes_rcItem_2.triggered.connect(lambda: self.rcAction_scenes("showInExplorerPB"))

        self.scenes_rcItem_3 = QtGui.QAction('Show Data Folder in Explorer', self)
        self.popMenu_scenes.addAction(self.scenes_rcItem_3)
        self.scenes_rcItem_3.triggered.connect(lambda: self.rcAction_scenes("showInExplorerData"))

        self.popMenu_scenes.addSeparator()
        self.scenes_rcItem_4 = QtGui.QAction('Scene Info', self)
        self.popMenu_scenes.addAction(self.scenes_rcItem_4)
        self.scenes_rcItem_4.triggered.connect(lambda: self.rcAction_scenes("showSceneInfo"))

        # Thumbnail Right Click Menu
        self.thumbnail_label.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.thumbnail_label.customContextMenuRequested.connect(self.onContextMenu_thumbnail)
        self.popMenu_thumbnail = QtGui.QMenu()

        rcAction_thumb_0 = QtGui.QAction('Replace with current view', self)
        self.popMenu_thumbnail.addAction(rcAction_thumb_0)
        rcAction_thumb_0.triggered.connect(lambda: self.rcAction_thumb("currentView"))


        rcAction_thumb_1 = QtGui.QAction('Replace with external file', self)
        self.popMenu_thumbnail.addAction(rcAction_thumb_1)
        rcAction_thumb_1.triggered.connect(lambda: self.rcAction_thumb("file"))


        # SHORTCUTS
        # ---------
        shortcutRefresh = QtGui.QShortcut(QtGui.QKeySequence("F5"), self, self.refresh)

        # SIGNAL CONNECTIONS
        # ------------------

        createProject_fm.triggered.connect(self.createProjectUI)

        add_remove_users_fm.triggered.connect(self.addRemoveUserUI)
        pb_settings_fm.triggered.connect(self.pbSettingsUI)
        add_remove_categories_fm.triggered.connect(self.addRemoveCategoryUI)

        projectSettings_fm.triggered.connect(self.projectSettingsUI)

        deleteFile_fm.triggered.connect(self.onDeleteBaseScene)

        deleteReference_fm.triggered.connect(self.onDeleteReference)

        checkReferences_fm.triggered.connect(lambda: self.populateBaseScenes(deepCheck=True))

        imanager.triggered.connect(self.onImanager)
        iviewer.triggered.connect(self.onIviewer)
        createPB.triggered.connect(self.manager.createPreview)


        self.statusBar().showMessage("Status | Idle")

        self.load_radioButton.clicked.connect(self.onModeChange)
        self.reference_radioButton.clicked.connect(self.onModeChange)

        self.category_tabWidget.currentChanged.connect(self.onCategoryChange)

        self.scenes_listWidget.currentItemChanged.connect(self.onBaseSceneChange)

        self.version_comboBox.activated.connect(self.onVersionChange)

        self.makeReference_pushButton.clicked.connect(self.onMakeReference)

        self.subProject_comboBox.activated.connect(self.onSubProjectChange)

        self.user_comboBox.activated.connect(self.onUserChange)

        self.showPreview_pushButton.clicked.connect(self.onShowPreview)

        self.addSubProject_pushButton.clicked.connect(self.createSubProjectUI)

        self.setProject_pushButton.clicked.connect(self.setProjectUI)

        self.saveBaseScene_pushButton.clicked.connect(self.saveBaseSceneDialog)
        saveBaseScene_fm.triggered.connect(self.saveBaseSceneDialog)

        self.saveVersion_pushButton.clicked.connect(self.saveAsVersionDialog)
        saveVersion_fm.triggered.connect(self.saveAsVersionDialog)

        self.scenes_listWidget.doubleClicked.connect(self.onLoadScene)
        self.loadScene_pushButton.clicked.connect(self.onLoadScene)

        self.addNote_pushButton.clicked.connect(self.addNoteDialog)





    def createSubProjectUI(self):

        newSub, ok = QtGui.QInputDialog.getText(self, "Create New Sub-Project", "Enter an unique Sub-Project name:")
        if ok:
            if self.manager._nameCheck(newSub):
                self.subProject_comboBox.clear()
                self.subProject_comboBox.addItems(self.manager.createSubproject(newSub))
                self.subProject_comboBox.setCurrentIndex(self.manager.currentSubIndex)
                self.populateBaseScenes()
                # self.onSubProjectChange()
            else:
                self.infoPop(textTitle="Naming Error", textHeader="Naming Error",
                             textInfo="Choose an unique name with latin characters without spaces", type="C")

    def createProjectUI(self):

        self.createproject_Dialog = QtGui.QDialog(parent=self)
        self.createproject_Dialog.setObjectName(("createproject_Dialog"))
        self.createproject_Dialog.resize(419, 300)
        self.createproject_Dialog.setWindowTitle(("Create New Project"))

        self.projectroot_label = QtGui.QLabel(self.createproject_Dialog)
        self.projectroot_label.setGeometry(QtCore.QRect(20, 30, 71, 20))
        self.projectroot_label.setText(("Project Path:"))
        self.projectroot_label.setObjectName(("projectpath_label"))

        currentProjects = os.path.abspath(os.path.join(self.manager.projectDir, os.pardir))
        self.projectroot_lineEdit = QtGui.QLineEdit(self.createproject_Dialog)
        self.projectroot_lineEdit.setGeometry(QtCore.QRect(90, 30, 241, 21))
        self.projectroot_lineEdit.setText((currentProjects))
        self.projectroot_lineEdit.setObjectName(("projectpath_lineEdit"))

        self.browse_pushButton = QtGui.QPushButton(self.createproject_Dialog)
        self.browse_pushButton.setText(("Browse"))
        self.browse_pushButton.setGeometry(QtCore.QRect(340, 30, 61, 21))
        self.browse_pushButton.setObjectName(("browse_pushButton"))

        self.resolvedpath_label = QtGui.QLabel(self.createproject_Dialog)
        self.resolvedpath_label.setGeometry(QtCore.QRect(20, 70, 381, 21))
        self.resolvedpath_label.setObjectName(("resolvedpath_label"))

        self.brandname_label = QtGui.QLabel(self.createproject_Dialog)
        self.brandname_label.setGeometry(QtCore.QRect(20, 110, 111, 20))
        self.brandname_label.setFrameShape(QtGui.QFrame.Box)
        self.brandname_label.setText(("Brand Name"))
        self.brandname_label.setAlignment(QtCore.Qt.AlignCenter)
        self.brandname_label.setObjectName(("brandname_label"))

        self.projectname_label = QtGui.QLabel(self.createproject_Dialog)
        self.projectname_label.setGeometry(QtCore.QRect(140, 110, 131, 20))
        self.projectname_label.setFrameShape(QtGui.QFrame.Box)
        self.projectname_label.setText(("Project Name"))
        self.projectname_label.setAlignment(QtCore.Qt.AlignCenter)
        self.projectname_label.setObjectName(("projectname_label"))

        self.client_label = QtGui.QLabel(self.createproject_Dialog)
        self.client_label.setGeometry(QtCore.QRect(280, 110, 121, 20))
        self.client_label.setFrameShape(QtGui.QFrame.Box)
        self.client_label.setText(("Client"))
        self.client_label.setAlignment(QtCore.Qt.AlignCenter)
        self.client_label.setObjectName(("client_label"))

        self.brandname_lineEdit = QtGui.QLineEdit(self.createproject_Dialog)
        self.brandname_lineEdit.setGeometry(QtCore.QRect(20, 140, 111, 21))
        self.brandname_lineEdit.setPlaceholderText(("(optional)"))
        self.brandname_lineEdit.setObjectName(("brandname_lineEdit"))

        self.projectname_lineEdit = QtGui.QLineEdit(self.createproject_Dialog)
        self.projectname_lineEdit.setGeometry(QtCore.QRect(140, 140, 131, 21))
        self.projectname_lineEdit.setPlaceholderText(("Mandatory Field"))
        self.projectname_lineEdit.setObjectName(("projectname_lineEdit"))

        self.client_lineEdit = QtGui.QLineEdit(self.createproject_Dialog)
        self.client_lineEdit.setGeometry(QtCore.QRect(280, 140, 121, 21))
        self.client_lineEdit.setPlaceholderText(("Mandatory Field"))
        self.client_lineEdit.setObjectName(("client_lineEdit"))

        resolution_label = QtGui.QLabel(self.createproject_Dialog)
        resolution_label.setGeometry(QtCore.QRect(24, 180 , 111, 21))
        resolution_label.setText("Resolution")

        resolutionX_spinBox = QtGui.QSpinBox(self.createproject_Dialog)
        resolutionX_spinBox.setGeometry(QtCore.QRect(80, 180, 60, 21))
        resolutionX_spinBox.setObjectName(("resolutionX_spinBox"))
        resolutionX_spinBox.setButtonSymbols(QtGui.QAbstractSpinBox.NoButtons)
        resolutionX_spinBox.setRange(1,99999)
        resolutionX_spinBox.setValue(1920)

        resolutionY_spinBox = QtGui.QSpinBox(self.createproject_Dialog)
        resolutionY_spinBox.setGeometry(QtCore.QRect(145, 180, 60, 21))
        resolutionY_spinBox.setObjectName(("resolutionY_spinBox"))
        resolutionY_spinBox.setButtonSymbols(QtGui.QAbstractSpinBox.NoButtons)
        resolutionY_spinBox.setRange(1,99999)
        resolutionY_spinBox.setValue(1080)

        fps_label = QtGui.QLabel(self.createproject_Dialog)
        fps_label.setGeometry(QtCore.QRect(54, 210 , 111, 21))
        fps_label.setText("FPS")

        fps_comboBox = QtGui.QComboBox(self.createproject_Dialog)
        fps_comboBox.setGeometry(QtCore.QRect(80, 210 , 60, 21))
        fps_comboBox.addItems(self.manager.fpsList)
        fps_comboBox.setCurrentIndex(2)

        self.createproject_buttonBox = QtGui.QDialogButtonBox(self.createproject_Dialog)
        self.createproject_buttonBox.setGeometry(QtCore.QRect(30, 250, 371, 32))
        self.createproject_buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.createproject_buttonBox.setStandardButtons(
            QtGui.QDialogButtonBox.Cancel | QtGui.QDialogButtonBox.Ok)
        self.createproject_buttonBox.setObjectName(("buttonBox"))

        self.cp_button = self.createproject_buttonBox.button(QtGui.QDialogButtonBox.Ok)
        self.cp_button.setText('Create Project')

        def browseProjectRoot():
            dlg = QtGui.QFileDialog()
            dlg.setFileMode(QtGui.QFileDialog.Directory)

            if dlg.exec_():
                selectedroot = os.path.normpath(dlg.selectedFiles()[0])
                self.projectroot_lineEdit.setText(selectedroot)
                resolve()

        def onCreateNewProject():
            root = self.projectroot_lineEdit.text()
            pName = self.projectname_lineEdit.text()
            bName = self.brandname_lineEdit.text()
            cName = self.client_lineEdit.text()
            # TODO : ref
            projectSettingsDB = {"Resolution": [resolutionX_spinBox.value(), resolutionY_spinBox.value()],
                                   "FPS": int(fps_comboBox.currentText())}
            pPath = self.manager.createNewProject(root, pName, bName, cName, settingsData=projectSettingsDB)
            self.manager.setProject(pPath)
            self.onProjectChange()
            self.createproject_Dialog.close()

        def resolve():
            if self.projectname_lineEdit.text() == "" or self.client_lineEdit.text() == "" or self.projectroot_lineEdit.text() == "":
                self.resolvedpath_label.setText("Fill the mandatory fields")
                self.newProjectPath = None
                return
            resolvedPath = self.manager._resolveProjectPath(self.projectroot_lineEdit.text(),
                                             self.projectname_lineEdit.text(),
                                             self.brandname_lineEdit.text(),
                                             self.client_lineEdit.text())
            self.resolvedpath_label.setText(resolvedPath)

        resolve()
        self.browse_pushButton.clicked.connect(browseProjectRoot)

        self.brandname_lineEdit.textEdited.connect(lambda: resolve())
        self.projectname_lineEdit.textEdited.connect(lambda: resolve())
        self.client_lineEdit.textEdited.connect(lambda: resolve())

        self.createproject_buttonBox.accepted.connect(onCreateNewProject)
        self.createproject_buttonBox.rejected.connect(self.createproject_Dialog.reject)

        self.brandname_lineEdit.textChanged.connect(
            lambda: self._checkValidity(self.brandname_lineEdit.text(), self.cp_button,
                                  self.brandname_lineEdit))
        self.projectname_lineEdit.textChanged.connect(
            lambda: self._checkValidity(self.projectname_lineEdit.text(), self.cp_button,
                                  self.projectname_lineEdit))
        self.client_lineEdit.textChanged.connect(
            lambda: self._checkValidity(self.client_lineEdit.text(), self.cp_button, self.client_lineEdit))

        self.createproject_Dialog.show()

    def setProjectUI(self):

        iconFont = QtGui.QFont()
        iconFont.setPointSize(12)
        iconFont.setBold(True)
        iconFont.setWeight(75)

        self.setProject_Dialog = QtGui.QDialog(parent=self)
        self.setProject_Dialog.setObjectName(("setProject_Dialog"))
        self.setProject_Dialog.resize(982, 450)
        self.setProject_Dialog.setWindowTitle(("Set Project"))

        gridLayout = QtGui.QGridLayout(self.setProject_Dialog)
        gridLayout.setObjectName(("gridLayout"))

        M1_horizontalLayout = QtGui.QHBoxLayout()
        M1_horizontalLayout.setObjectName(("M1_horizontalLayout"))

        lookIn_label = QtGui.QLabel(self.setProject_Dialog)
        lookIn_label.setText(("Look in:"))
        lookIn_label.setObjectName(("lookIn_label"))

        M1_horizontalLayout.addWidget(lookIn_label)

        self.lookIn_lineEdit = QtGui.QLineEdit(self.setProject_Dialog)
        self.lookIn_lineEdit.setText((""))
        self.lookIn_lineEdit.setPlaceholderText((""))
        self.lookIn_lineEdit.setObjectName(("lookIn_lineEdit"))

        M1_horizontalLayout.addWidget(self.lookIn_lineEdit)

        browse_pushButton = QtGui.QPushButton(self.setProject_Dialog)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(browse_pushButton.sizePolicy().hasHeightForWidth())
        browse_pushButton.setSizePolicy(sizePolicy)
        browse_pushButton.setMaximumSize(QtCore.QSize(50, 16777215))
        browse_pushButton.setText("Browse")
        browse_pushButton.setObjectName(("browse_pushButton"))

        M1_horizontalLayout.addWidget(browse_pushButton)

        self.back_pushButton = QtGui.QPushButton(self.setProject_Dialog)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.back_pushButton.sizePolicy().hasHeightForWidth())
        self.back_pushButton.setSizePolicy(sizePolicy)
        self.back_pushButton.setMaximumSize(QtCore.QSize(30, 16777215))
        self.back_pushButton.setFont(iconFont)
        self.back_pushButton.setText(("<"))
        self.back_pushButton.setShortcut((""))
        self.back_pushButton.setObjectName(("back_pushButton"))

        M1_horizontalLayout.addWidget(self.back_pushButton)

        self.forward_pushButton = QtGui.QPushButton(self.setProject_Dialog)
        self.forward_pushButton.setMaximumSize(QtCore.QSize(30, 16777215))
        self.forward_pushButton.setFont(iconFont)
        self.forward_pushButton.setText((">"))
        self.forward_pushButton.setShortcut((""))
        self.forward_pushButton.setObjectName(("forward_pushButton"))

        M1_horizontalLayout.addWidget(self.forward_pushButton)

        up_pushButton = QtGui.QPushButton(self.setProject_Dialog)
        up_pushButton.setMaximumSize(QtCore.QSize(30, 16777215))
        up_pushButton.setText(("Up"))
        up_pushButton.setShortcut((""))
        up_pushButton.setObjectName(("up_pushButton"))

        M1_horizontalLayout.addWidget(up_pushButton)

        gridLayout.addLayout(M1_horizontalLayout, 0, 0, 1, 1)

        M2_horizontalLayout = QtGui.QHBoxLayout()
        M2_horizontalLayout.setObjectName(("M2_horizontalLayout"))

        M2_splitter = QtGui.QSplitter(self.setProject_Dialog)
        M2_splitter.setHandleWidth(10)
        M2_splitter.setObjectName(("M2_splitter"))


        # self.folders_tableView = QtWidgets.QTableView(self.M2_splitter)
        self.folders_tableView = QtGui.QTreeView(M2_splitter)
        self.folders_tableView.setMinimumSize(QtCore.QSize(0, 0))
        self.folders_tableView.setDragEnabled(True)
        self.folders_tableView.setDragDropMode(QtGui.QAbstractItemView.DragOnly)
        self.folders_tableView.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.folders_tableView.setObjectName(("folders_tableView"))

        self.folders_tableView.setFrameShape(QtGui.QFrame.NoFrame)
        self.folders_tableView.setItemsExpandable(False)
        self.folders_tableView.setRootIsDecorated(False)
        self.folders_tableView.setSortingEnabled(True)
        self.folders_tableView.sortByColumn(0, QtCore.Qt.SortOrder.AscendingOrder)


        verticalLayoutWidget = QtGui.QWidget(M2_splitter)
        verticalLayoutWidget.setObjectName(("verticalLayoutWidget"))

        M2_S2_verticalLayout = QtGui.QVBoxLayout(verticalLayoutWidget)
        M2_S2_verticalLayout.setContentsMargins(0, 10, 0, 10)
        M2_S2_verticalLayout.setSpacing(6)
        M2_S2_verticalLayout.setObjectName(("M2_S2_verticalLayout"))

        favorites_label = QtGui.QLabel(verticalLayoutWidget)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(True)
        font.setWeight(75)
        favorites_label.setFont(font)
        favorites_label.setText(("Bookmarks:"))
        favorites_label.setObjectName(("favorites_label"))

        M2_S2_verticalLayout.addWidget(favorites_label)

        self.favorites_listWidget = DropListWidget(verticalLayoutWidget)
        self.favorites_listWidget.setAlternatingRowColors(True)
        self.favorites_listWidget.setObjectName(("favorites_listWidget"))

        M2_S2_verticalLayout.addWidget(self.favorites_listWidget)
        M2_S2_horizontalLayout = QtGui.QHBoxLayout()
        M2_S2_horizontalLayout.setObjectName(("M2_S2_horizontalLayout"))

        spacerItem = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)

        M2_S2_horizontalLayout.addItem(spacerItem)

        remove_pushButton = QtGui.QPushButton(verticalLayoutWidget)
        remove_pushButton.setMaximumSize(QtCore.QSize(35, 35))
        remove_pushButton.setFont(iconFont)
        remove_pushButton.setText(("-"))
        remove_pushButton.setObjectName(("remove_pushButton"))

        M2_S2_horizontalLayout.addWidget(remove_pushButton)

        add_pushButton = QtGui.QPushButton(verticalLayoutWidget)
        add_pushButton.setMaximumSize(QtCore.QSize(35, 35))
        add_pushButton.setFont(iconFont)
        add_pushButton.setText(("+"))
        add_pushButton.setObjectName(("add_pushButton"))

        M2_S2_horizontalLayout.addWidget(add_pushButton)

        M2_S2_verticalLayout.addLayout(M2_S2_horizontalLayout)

        M2_horizontalLayout.addWidget(M2_splitter)

        gridLayout.addLayout(M2_horizontalLayout, 1, 0, 1, 1)

        M3_horizontalLayout = QtGui.QHBoxLayout()

        M3_horizontalLayout.setContentsMargins(0, 20, -1, -1)

        M3_horizontalLayout.setObjectName(("M3_horizontalLayout"))

        spacerItem1 = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)

        M3_horizontalLayout.addItem(spacerItem1)

        cancel_pushButton = QtGui.QPushButton(self.setProject_Dialog)
        cancel_pushButton.setMaximumSize(QtCore.QSize(70, 16777215))
        cancel_pushButton.setText("Cancel")
        cancel_pushButton.setObjectName(("cancel_pushButton"))

        M3_horizontalLayout.addWidget(cancel_pushButton, QtCore.Qt.AlignRight)

        set_pushButton = QtGui.QPushButton(self.setProject_Dialog)
        set_pushButton.setMaximumSize(QtCore.QSize(70, 16777215))
        set_pushButton.setText("Set")
        set_pushButton.setObjectName(("set_pushButton"))

        M3_horizontalLayout.addWidget(set_pushButton, QtCore.Qt.AlignRight)

        gridLayout.addLayout(M3_horizontalLayout, 2, 0, 1, 1)

        verticalLayoutWidget.raise_()

        M2_splitter.setStretchFactor(0,1)

        ## Initial Stuff
        self.projectsRoot = os.path.abspath(os.path.join(self.manager.projectDir, os.pardir))
        self.browser = Browse()
        self.spActiveProjectPath = None
        self.__flagView = True

        self.setPmodel = QtGui.QFileSystemModel()
        self.setPmodel.setRootPath(self.projectsRoot)
        self.setPmodel.setFilter(QtCore.QDir.AllDirs | QtCore.QDir.NoDotAndDotDot | QtCore.QDir.Time)

        self.folders_tableView.setModel(self.setPmodel)
        self.folders_tableView.setRootIndex(self.setPmodel.index(self.projectsRoot))
        self.folders_tableView.hideColumn(1)
        self.folders_tableView.hideColumn(2)
        self.folders_tableView.setColumnWidth(0,400)

        self.favList = self.manager._loadFavorites()
        self.favorites_listWidget.addItems([x[0] for x in self.favList])

        self.lookIn_lineEdit.setText(self.projectsRoot)

        def navigate(command, index=None):
            if command == "init":
                # feed the initial data
                self.browser.addData(self.projectsRoot)

            if command == "up":
                self.projectsRoot = os.path.abspath(os.path.join(self.projectsRoot, os.pardir))
                self.browser.addData(self.projectsRoot)

            if command == "back":
                self.browser.backward()

            if command == "forward":
                self.browser.forward()

            if command == "browse":
                dir = str(QtGui.QFileDialog.getExistingDirectory(self, "Select Directory"))
                if dir:
                    self.projectsRoot = dir
                    self.browser.addData(self.projectsRoot)

                else:
                    return

            if command == "folder":
                index = self.folders_tableView.currentIndex()
                self.projectsRoot = os.path.normpath((self.setPmodel.filePath(index)))
                self.browser.addData(self.projectsRoot)

            if command == "lineEnter":
                dir = self.lookIn_lineEdit.text()
                if os.path.isdir(dir):
                    self.projectsRoot = dir
                    self.browser.addData(self.projectsRoot)

                else:
                    self.lookIn_lineEdit.setText(self.projectsRoot)

            self.setPmodel.setRootPath(self.projectsRoot)

            self.forward_pushButton.setDisabled(self.browser.isForwardLocked())
            self.back_pushButton.setDisabled(self.browser.isBackwardLocked())
            self.folders_tableView.setRootIndex(self.setPmodel.index(self.browser.getData()))
            self.lookIn_lineEdit.setText(self.browser.getData())

        def onRemoveFavs():

            row = self.favorites_listWidget.currentRow()
            print row
            if row == -1:
                return
            # item = self.favList[row]
            self.favList = self.manager._removeFromFavorites(row)
            # block the signal to prevent unwanted cycle

            self.favorites_listWidget.blockSignals(True)
            self.favorites_listWidget.takeItem(row)
            self.favorites_listWidget.blockSignals(False)

        def onAddFavs():
            index = self.folders_tableView.currentIndex()
            if index.row() == -1:  # no row selected, abort
                return
            fullPath = self.setPmodel.filePath(index)
            onDragAndDrop(fullPath)

        def onDragAndDrop(path):
            normPath = os.path.normpath(path)

            path, fName = os.path.split(normPath)
            if [fName, normPath] in self.favList:
                return
            self.favorites_listWidget.addItem(fName)
            self.favList = self.manager._addToFavorites(fName, normPath)

        def favoritesActivated():
            # block the signal to prevent unwanted cycle
            self.folders_tableView.selectionModel().blockSignals(True)
            row = self.favorites_listWidget.currentRow()
            self.spActiveProjectPath = self.favList[row][1]

            # clear the selection in folders view
            self.folders_tableView.setCurrentIndex(self.setPmodel.index(self.projectsRoot))
            self.folders_tableView.selectionModel().blockSignals(False)

        def foldersViewActivated():
            # block the signal to prevent unwanted cycle
            self.favorites_listWidget.blockSignals(True)
            index = self.folders_tableView.currentIndex()
            self.spActiveProjectPath = os.path.normpath((self.setPmodel.filePath(index)))


            # clear the selection in favorites view
            self.favorites_listWidget.setCurrentRow(-1)
            self.favorites_listWidget.blockSignals(False)

        def setProject():
            self.manager.setProject(self.spActiveProjectPath)
            self.onProjectChange()
            self.setProject_Dialog.close()

        navigate("init")

        ## SIGNALS & SLOTS
        self.favorites_listWidget.dropped.connect(lambda path: onDragAndDrop(path))
        remove_pushButton.clicked.connect(onRemoveFavs)
        add_pushButton.clicked.connect(onAddFavs)

        self.favorites_listWidget.doubleClicked.connect(setProject)

        up_pushButton.clicked.connect(lambda: navigate("up"))
        self.back_pushButton.clicked.connect(lambda: navigate("back"))
        self.forward_pushButton.clicked.connect(lambda: navigate("forward"))
        browse_pushButton.clicked.connect(lambda: navigate("browse"))
        self.lookIn_lineEdit.returnPressed.connect(lambda: navigate("lineEnter"))
        self.folders_tableView.doubleClicked.connect(lambda index: navigate("folder", index=index))


        self.favorites_listWidget.currentItemChanged.connect(favoritesActivated)
        # self.folders_tableView.selectionModel().currentRowChanged.connect(foldersViewActivated)
        # There is a bug in here. If following two lines are run in a single line, a segmentation fault occurs and crashes 3ds max immediately
        selectionModel = self.folders_tableView.selectionModel()
        selectionModel.selectionChanged.connect(foldersViewActivated)


        self.favorites_listWidget.doubleClicked.connect(setProject)
        #
        cancel_pushButton.clicked.connect(self.setProject_Dialog.close)
        set_pushButton.clicked.connect(setProject)
        # set_pushButton.clicked.connect(self.setProject_Dialog.close)
        #
        self.setProject_Dialog.show()

    def pbSettingsUI(self):

        admin_pswd = "682"
        passw, ok = QtGui.QInputDialog.getText(self, "Password Query", "Enter Admin Password:",
                                               QtGui.QLineEdit.Password)
        if ok:
            if passw == admin_pswd:
                pass
            else:
                self.infoPop(textTitle="Incorrect Password", textHeader="The Password is invalid")
                return
        else:
            return





        # formatDict = self.manager.getFormatsAndCodecs()

        # def updateCodecs():
        #     codecList = formatDict[self.fileformat_comboBox.currentText()]
        #     self.codec_comboBox.clear()
        #
        #     self.codec_comboBox.addItems(codecList)

        def onPbSettingsAccept():
            newPbSettings = {"Resolution": (self.resolutionx_spinBox.value(), self.resolutiony_spinBox.value()),
                             "Format": "avi",
                             "Codec": "N/A",
                             "Percent": 100,  ## this one never changes
                             "Quality": "N/A",
                             "ShowFrameNumber": self.showframenumber_checkBox.isChecked(),
                             "ShowSceneName": "N/A",
                             "ShowCategory": "N/A",
                             "ShowFPS": "N/A",
                             "ShowFrameRange": "N/A",
                             "PolygonOnly": self.polygononly_checkBox.isChecked(),
                             "ShowGrid": self.showgrid_checkBox.isChecked(),
                             "ClearSelection": self.clearselection_checkBox.isChecked(),
                             "DisplayTextures": "N/A",
                             "WireOnShaded": self.wireonshaded_checkBox.isChecked(),
                             "UseDefaultMaterial": "N/A"
                             }
            self.manager._savePBSettings(newPbSettings)
            self.statusBar().showMessage("Status | Playblast Settings Saved")
            self.pbSettings_dialog.accept()

        currentSettings = self.manager._loadPBSettings()

        self.pbSettings_dialog = QtGui.QDialog(parent=self)
        self.pbSettings_dialog.setModal(True)
        self.pbSettings_dialog.setObjectName(("Playblast_Dialog"))
        self.pbSettings_dialog.resize(380, 483)
        self.pbSettings_dialog.setMaximumSize(QtCore.QSize(380, 400))
        self.pbSettings_dialog.setWindowTitle(("Set Playblast Settings"))

        self.pbsettings_buttonBox = QtGui.QDialogButtonBox(self.pbSettings_dialog)
        self.pbsettings_buttonBox.setGeometry(QtCore.QRect(20, 345, 341, 30))
        self.pbsettings_buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.pbsettings_buttonBox.setStandardButtons(
            QtGui.QDialogButtonBox.Cancel | QtGui.QDialogButtonBox.Save)
        self.pbsettings_buttonBox.setObjectName(("pbsettings_buttonBox"))

        self.videoproperties_groupBox = QtGui.QGroupBox(self.pbSettings_dialog)
        self.videoproperties_groupBox.setGeometry(QtCore.QRect(10, 20, 361, 80))
        self.videoproperties_groupBox.setTitle(("Video Properties"))
        self.videoproperties_groupBox.setObjectName(("videoproperties_groupBox"))

        # self.fileformat_label = QtGui.QLabel(self.videoproperties_groupBox)
        # self.fileformat_label.setGeometry(QtCore.QRect(20, 30, 71, 20))
        # self.fileformat_label.setFrameShape(QtGui.QFrame.NoFrame)
        # self.fileformat_label.setFrameShadow(QtGui.QFrame.Plain)
        # self.fileformat_label.setText(("Format"))
        # self.fileformat_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing | QtCore.Qt.AlignVCenter)
        # self.fileformat_label.setObjectName(("fileformat_label"))

        # self.fileformat_comboBox = QtGui.QComboBox(self.videoproperties_groupBox)
        # self.fileformat_comboBox.setGeometry(QtCore.QRect(100, 30, 111, 22))
        # self.fileformat_comboBox.setObjectName(("fileformat_comboBox"))
        # self.fileformat_comboBox.addItems(formatDict.keys())

        # get the index number from the name in the settings file and make that index active
        # ffindex = self.fileformat_comboBox.findText(currentSettings["Format"], QtCore.Qt.MatchFixedString)
        # if ffindex >= 0:
        #     self.fileformat_comboBox.setCurrentIndex(ffindex)

        # self.codec_label = QtGui.QLabel(self.videoproperties_groupBox)
        # self.codec_label.setGeometry(QtCore.QRect(30, 70, 61, 20))
        # self.codec_label.setFrameShape(QtGui.QFrame.NoFrame)
        # self.codec_label.setFrameShadow(QtGui.QFrame.Plain)
        # self.codec_label.setText(("Codec"))
        # self.codec_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing | QtCore.Qt.AlignVCenter)
        # self.codec_label.setObjectName(("codec_label"))

        # self.codec_comboBox = QtGui.QComboBox(self.videoproperties_groupBox)
        # self.codec_comboBox.setGeometry(QtCore.QRect(100, 70, 111, 22))
        # self.codec_comboBox.setObjectName(("codec_comboBox"))
        # updateCodecs()

        # self.fileformat_comboBox.currentIndexChanged.connect(updateCodecs)

        # get the index number from the name in the settings file and make that index active
        # cindex = self.codec_comboBox.findText(currentSettings["Codec"], QtCore.Qt.MatchFixedString)
        # if cindex >= 0:
        #     self.codec_comboBox.setCurrentIndex(cindex)

        # self.quality_label = QtGui.QLabel(self.videoproperties_groupBox)
        # self.quality_label.setGeometry(QtCore.QRect(30, 110, 61, 20))
        # self.quality_label.setFrameShape(QtGui.QFrame.NoFrame)
        # self.quality_label.setFrameShadow(QtGui.QFrame.Plain)
        # self.quality_label.setText(("Quality"))
        # self.quality_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing | QtCore.Qt.AlignVCenter)
        # self.quality_label.setObjectName(("quality_label"))

        # self.quality_spinBox = QtGui.QSpinBox(self.videoproperties_groupBox)
        # self.quality_spinBox.setGeometry(QtCore.QRect(100, 110, 41, 21))
        # self.quality_spinBox.setButtonSymbols(QtGui.QAbstractSpinBox.NoButtons)
        # self.quality_spinBox.setMinimum(1)
        # self.quality_spinBox.setMaximum(100)
        # self.quality_spinBox.setProperty("value", currentSettings["Quality"])
        # self.quality_spinBox.setObjectName(("quality_spinBox"))

        # self.quality_horizontalSlider = QtGui.QSlider(self.videoproperties_groupBox)
        # self.quality_horizontalSlider.setGeometry(QtCore.QRect(150, 110, 191, 21))
        # self.quality_horizontalSlider.setMinimum(1)
        # self.quality_horizontalSlider.setMaximum(100)
        # self.quality_horizontalSlider.setProperty("value", currentSettings["Quality"])
        # self.quality_horizontalSlider.setOrientation(QtCore.Qt.Horizontal)
        # self.quality_horizontalSlider.setTickInterval(0)
        # self.quality_horizontalSlider.setObjectName(("quality_horizontalSlider"))

        self.resolution_label = QtGui.QLabel(self.videoproperties_groupBox)
        self.resolution_label.setGeometry(QtCore.QRect(30, 30, 61, 20))
        self.resolution_label.setFrameShape(QtGui.QFrame.NoFrame)
        self.resolution_label.setFrameShadow(QtGui.QFrame.Plain)
        self.resolution_label.setText(("Resolution"))
        self.resolution_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing | QtCore.Qt.AlignVCenter)
        self.resolution_label.setObjectName(("resolution_label"))

        self.resolutionx_spinBox = QtGui.QSpinBox(self.videoproperties_groupBox)
        self.resolutionx_spinBox.setGeometry(QtCore.QRect(100, 30, 61, 21))
        self.resolutionx_spinBox.setButtonSymbols(QtGui.QAbstractSpinBox.NoButtons)
        self.resolutionx_spinBox.setMinimum(0)
        self.resolutionx_spinBox.setMaximum(4096)
        self.resolutionx_spinBox.setProperty("value", currentSettings["Resolution"][0])
        self.resolutionx_spinBox.setObjectName(("resolutionx_spinBox"))

        self.resolutiony_spinBox = QtGui.QSpinBox(self.videoproperties_groupBox)
        self.resolutiony_spinBox.setGeometry(QtCore.QRect(170, 30, 61, 21))
        self.resolutiony_spinBox.setButtonSymbols(QtGui.QAbstractSpinBox.NoButtons)
        self.resolutiony_spinBox.setMinimum(1)
        self.resolutiony_spinBox.setMaximum(4096)
        self.resolutiony_spinBox.setProperty("value", currentSettings["Resolution"][1])
        self.resolutiony_spinBox.setObjectName(("resolutiony_spinBox"))

        self.viewportoptions_groupBox = QtGui.QGroupBox(self.pbSettings_dialog)
        self.viewportoptions_groupBox.setGeometry(QtCore.QRect(10, 120, 361, 95))
        self.viewportoptions_groupBox.setTitle(("Viewport Options"))
        self.viewportoptions_groupBox.setObjectName(("viewportoptions_groupBox"))

        self.polygononly_checkBox = QtGui.QCheckBox(self.viewportoptions_groupBox)
        self.polygononly_checkBox.setGeometry(QtCore.QRect(60, 30, 91, 20))
        self.polygononly_checkBox.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.polygononly_checkBox.setText(("Polygon Only"))
        self.polygononly_checkBox.setChecked(currentSettings["PolygonOnly"])
        self.polygononly_checkBox.setObjectName(("polygononly_checkBox"))

        self.showgrid_checkBox = QtGui.QCheckBox(self.viewportoptions_groupBox)
        self.showgrid_checkBox.setGeometry(QtCore.QRect(210, 30, 91, 20))
        self.showgrid_checkBox.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.showgrid_checkBox.setText(("Show Grid"))
        self.showgrid_checkBox.setChecked(currentSettings["ShowGrid"])
        self.showgrid_checkBox.setObjectName(("showgrid_checkBox"))

        self.clearselection_checkBox = QtGui.QCheckBox(self.viewportoptions_groupBox)
        self.clearselection_checkBox.setGeometry(QtCore.QRect(60, 60, 91, 20))
        self.clearselection_checkBox.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.clearselection_checkBox.setText(("Clear Selection"))
        self.clearselection_checkBox.setChecked(currentSettings["ClearSelection"])
        self.clearselection_checkBox.setObjectName(("clearselection_checkBox"))

        self.wireonshaded_checkBox = QtGui.QCheckBox(self.viewportoptions_groupBox)
        self.wireonshaded_checkBox.setGeometry(QtCore.QRect(201, 60, 100, 20))
        self.wireonshaded_checkBox.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.wireonshaded_checkBox.setText(("Wire On Shaded"))
        try:
            self.wireonshaded_checkBox.setChecked(currentSettings["WireOnShaded"])
        except KeyError:
            self.wireonshaded_checkBox.setChecked(False)
        self.wireonshaded_checkBox.setObjectName(("wireonshaded_checkBox"))

        # self.usedefaultmaterial_checkBox = QtGui.QCheckBox(self.viewportoptions_groupBox)
        # self.usedefaultmaterial_checkBox.setGeometry(QtCore.QRect(180, 90, 120, 20))
        # self.usedefaultmaterial_checkBox.setLayoutDirection(QtCore.Qt.RightToLeft)
        # self.usedefaultmaterial_checkBox.setText(("Use Default Material"))
        # try:
        #     self.usedefaultmaterial_checkBox.setChecked(currentSettings["UseDefaultMaterial"])
        # except KeyError:
        #     self.usedefaultmaterial_checkBox.setChecked(False)

        # self.displaytextures_checkBox = QtGui.QCheckBox(self.viewportoptions_groupBox)
        # self.displaytextures_checkBox.setGeometry(QtCore.QRect(190, 60, 111, 20))
        # self.displaytextures_checkBox.setLayoutDirection(QtCore.Qt.RightToLeft)
        # self.displaytextures_checkBox.setText(("Display Textures"))
        # self.displaytextures_checkBox.setChecked(currentSettings["DisplayTextures"])
        # self.displaytextures_checkBox.setObjectName(("displaytextures_checkBox"))

        self.hudoptions_groupBox = QtGui.QGroupBox(self.pbSettings_dialog)
        self.hudoptions_groupBox.setGeometry(QtCore.QRect(10, 240, 361, 80))
        self.hudoptions_groupBox.setTitle(("HUD Options"))
        self.hudoptions_groupBox.setObjectName(("hudoptions_groupBox"))

        self.showframenumber_checkBox = QtGui.QCheckBox(self.hudoptions_groupBox)
        self.showframenumber_checkBox.setGeometry(QtCore.QRect(20, 20, 131, 20))
        self.showframenumber_checkBox.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.showframenumber_checkBox.setText(("Show Frame Number"))
        self.showframenumber_checkBox.setChecked(currentSettings["ShowFrameNumber"])
        self.showframenumber_checkBox.setObjectName(("showframenumber_checkBox"))

        # self.showscenename_checkBox = QtGui.QCheckBox(self.hudoptions_groupBox)
        # self.showscenename_checkBox.setGeometry(QtCore.QRect(20, 50, 131, 20))
        # self.showscenename_checkBox.setLayoutDirection(QtCore.Qt.RightToLeft)
        # self.showscenename_checkBox.setText(("Show Scene Name"))
        # self.showscenename_checkBox.setChecked(currentSettings["ShowSceneName"])
        # self.showscenename_checkBox.setObjectName(("showscenename_checkBox"))

        # self.showcategory_checkBox = QtGui.QCheckBox(self.hudoptions_groupBox)
        # self.showcategory_checkBox.setGeometry(QtCore.QRect(200, 20, 101, 20))
        # self.showcategory_checkBox.setLayoutDirection(QtCore.Qt.RightToLeft)
        # self.showcategory_checkBox.setText(("Show Category"))
        # self.showcategory_checkBox.setChecked(currentSettings["ShowCategory"])
        # self.showcategory_checkBox.setObjectName(("showcategory_checkBox"))

        # self.showfps_checkBox = QtGui.QCheckBox(self.hudoptions_groupBox)
        # self.showfps_checkBox.setGeometry(QtCore.QRect(200, 50, 101, 20))
        # self.showfps_checkBox.setLayoutDirection(QtCore.Qt.RightToLeft)
        # self.showfps_checkBox.setText(("Show FPS"))
        # self.showfps_checkBox.setChecked(currentSettings["ShowFPS"])
        # self.showfps_checkBox.setObjectName(("showfps_checkBox"))

        # self.showframerange_checkBox = QtGui.QCheckBox(self.hudoptions_groupBox)
        # self.showframerange_checkBox.setGeometry(QtCore.QRect(20, 80, 131, 20))
        # self.showframerange_checkBox.setLayoutDirection(QtCore.Qt.RightToLeft)
        # self.showframerange_checkBox.setText(("Show Frame Range"))
        # v1.1 SPECIFIC
        # try:
        #     self.showframerange_checkBox.setChecked(currentSettings["ShowFrameRange"])
        # except KeyError:
        #     self.showframerange_checkBox.setChecked(True)
        # self.showframerange_checkBox.setObjectName(("showframerange_checkBox"))

        self.pbsettings_buttonBox.accepted.connect(onPbSettingsAccept)
        self.pbsettings_buttonBox.rejected.connect(self.pbSettings_dialog.reject)
        # self.quality_spinBox.valueChanged.connect(self.quality_horizontalSlider.setValue)
        # self.quality_horizontalSlider.valueChanged.connect(self.quality_spinBox.setValue)

        self.pbSettings_dialog.show()

    def addRemoveUserUI(self):

        admin_pswd = "682"
        passw, ok = QtGui.QInputDialog.getText(self, "Password Query", "Enter Admin Password:",
                                               QtGui.QLineEdit.Password)
        if ok:
            if passw == admin_pswd:
                pass
            else:
                self.infoPop(textTitle="Incorrect Password", textHeader="The Password is invalid")
                return
        else:
            return

        users_Dialog = QtGui.QDialog(parent=self)
        users_Dialog.setModal(True)
        users_Dialog.setObjectName(("users_Dialog"))
        users_Dialog.resize(380, 483)
        users_Dialog.setMinimumSize(QtCore.QSize(342, 177))
        users_Dialog.setMaximumSize(QtCore.QSize(342, 177))
        users_Dialog.setWindowTitle(("Add/Remove Users"))
        users_Dialog.setFocus()

        addnewuser_groupBox = QtGui.QGroupBox(users_Dialog)
        addnewuser_groupBox.setGeometry(QtCore.QRect(10, 10, 321, 91))
        addnewuser_groupBox.setTitle(("Add New User"))
        addnewuser_groupBox.setObjectName(("addnewuser_groupBox"))

        fullname_label = QtGui.QLabel(addnewuser_groupBox)
        fullname_label.setGeometry(QtCore.QRect(0, 30, 81, 21))
        fullname_label.setLayoutDirection(QtCore.Qt.LeftToRight)
        fullname_label.setText(("Full Name:"))
        fullname_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing | QtCore.Qt.AlignVCenter)
        fullname_label.setObjectName(("fullname_label"))

        self.fullname_lineEdit = QtGui.QLineEdit(addnewuser_groupBox)
        self.fullname_lineEdit.setGeometry(QtCore.QRect(90, 30, 151, 20))
        self.fullname_lineEdit.setPlaceholderText(("e.g \"John Doe\""))
        self.fullname_lineEdit.setObjectName(("fullname_lineEdit"))

        initials_label = QtGui.QLabel(addnewuser_groupBox)
        initials_label.setGeometry(QtCore.QRect(0, 60, 81, 21))
        initials_label.setLayoutDirection(QtCore.Qt.LeftToRight)
        initials_label.setText(("Initials:"))
        initials_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing | QtCore.Qt.AlignVCenter)
        initials_label.setObjectName(("initials_label"))

        self.initials_lineEdit = QtGui.QLineEdit(addnewuser_groupBox)
        self.initials_lineEdit.setGeometry(QtCore.QRect(90, 60, 151, 20))
        self.initials_lineEdit.setText((""))
        self.initials_lineEdit.setPlaceholderText(("e.g \"jd\" (must be unique)"))
        self.initials_lineEdit.setObjectName(("initials_lineEdit"))

        addnewuser_pushButton = QtGui.QPushButton(addnewuser_groupBox)
        addnewuser_pushButton.setGeometry(QtCore.QRect(250, 30, 61, 51))
        addnewuser_pushButton.setText(("Add"))
        addnewuser_pushButton.setObjectName(("addnewuser_pushButton"))

        deleteuser_groupBox = QtGui.QGroupBox(users_Dialog)
        deleteuser_groupBox.setGeometry(QtCore.QRect(10, 110, 321, 51))
        deleteuser_groupBox.setTitle(("Delete User"))
        deleteuser_groupBox.setObjectName(("deleteuser_groupBox"))

        self.selectuser_comboBox = QtGui.QComboBox(deleteuser_groupBox)
        self.selectuser_comboBox.setGeometry(QtCore.QRect(10, 20, 231, 22))
        self.selectuser_comboBox.setObjectName(("selectuser_comboBox"))

        userListSorted = sorted(self.manager._usersDict.keys())
        for num in range(len(userListSorted)):
            self.selectuser_comboBox.addItem((userListSorted[num]))
            self.selectuser_comboBox.setItemText(num, (userListSorted[num]))

        deleteuser_pushButton = QtGui.QPushButton(deleteuser_groupBox)
        deleteuser_pushButton.setGeometry(QtCore.QRect(250, 20, 61, 21))
        deleteuser_pushButton.setText(("Delete"))
        deleteuser_pushButton.setObjectName(("deleteuser_pushButton"))


        def onAddUser():
            ret, msg = self.manager.addUser(self.fullname_lineEdit.text(), self.initials_lineEdit.text())
            if ret == -1:
                self.infoPop(textTitle="Cannot Add User", textHeader=msg)
                return
            self.manager.currentUser = self.fullname_lineEdit.text()
            self._initUsers()
            userListSorted = sorted(self.manager._usersDict.keys())
            self.selectuser_comboBox.clear()
            for num in range(len(userListSorted)):
                self.selectuser_comboBox.addItem((userListSorted[num]))
                self.selectuser_comboBox.setItemText(num, (userListSorted[num]))
            self.statusBar().showMessage("Status | User Added => %s" % self.fullname_lineEdit.text())
            self.fullname_lineEdit.setText("")
            self.initials_lineEdit.setText("")

            pass

        def onRemoveUser():
            self.manager.removeUser(self.selectuser_comboBox.currentText())
            self.manager.currentUser = self.manager._usersDict.keys()[0]
            self._initUsers()
            userListSorted = sorted(self.manager._usersDict.keys())
            self.selectuser_comboBox.clear()
            for num in range(len(userListSorted)):
                self.selectuser_comboBox.addItem((userListSorted[num]))
                self.selectuser_comboBox.setItemText(num, (userListSorted[num]))
            pass

        addnewuser_pushButton.clicked.connect(onAddUser)
        deleteuser_pushButton.clicked.connect(onRemoveUser)

        self.fullname_lineEdit.textChanged.connect(
            lambda: self._checkValidity(self.fullname_lineEdit.text(), addnewuser_pushButton,
                                  self.fullname_lineEdit, allowSpaces=True))
        self.initials_lineEdit.textChanged.connect(
            lambda: self._checkValidity(self.initials_lineEdit.text(), addnewuser_pushButton,
                                  self.initials_lineEdit))

        users_Dialog.show()

    def addRemoveCategoryUI(self):

        admin_pswd = "682"
        passw, ok = QtGui.QInputDialog.getText(self, "Password Query", "Enter Admin Password:",
                                               QtGui.QLineEdit.Password)
        if ok:
            if passw == admin_pswd:
                pass
            else:
                self.infoPop(textTitle="Incorrect Password", textHeader="The Password is invalid")
                return
        else:
            return

        categories_dialog = QtGui.QDialog(parent=self)
        categories_dialog.setModal(True)
        categories_dialog.setObjectName(("category_Dialog"))
        categories_dialog.setMinimumSize(QtCore.QSize(342, 177))
        categories_dialog.setMaximumSize(QtCore.QSize(342, 177))
        categories_dialog.setWindowTitle(("Add/Remove Categories"))
        categories_dialog.setFocus()

        addnewcategory_groupbox = QtGui.QGroupBox(categories_dialog)
        addnewcategory_groupbox.setGeometry(QtCore.QRect(10, 10, 321, 81))
        addnewcategory_groupbox.setTitle(("Add New Category"))
        addnewcategory_groupbox.setObjectName(("addnewcategory_groupBox"))

        categoryName_label = QtGui.QLabel(addnewcategory_groupbox)
        categoryName_label.setGeometry(QtCore.QRect(10, 30, 81, 21))
        categoryName_label.setLayoutDirection(QtCore.Qt.LeftToRight)
        categoryName_label.setText(("Category Name:"))
        categoryName_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing | QtCore.Qt.AlignVCenter)
        categoryName_label.setObjectName(("categoryName_label"))

        self.categoryName_lineEdit= QtGui.QLineEdit(addnewcategory_groupbox)
        self.categoryName_lineEdit.setGeometry(QtCore.QRect(105, 30, 135, 20))
        self.categoryName_lineEdit.setPlaceholderText(("e.g \"Look Dev\""))
        self.categoryName_lineEdit.setObjectName(("categoryName_lineEdit"))

        addnewcategory_pushButton = QtGui.QPushButton(addnewcategory_groupbox)
        addnewcategory_pushButton.setGeometry(QtCore.QRect(250, 28, 61, 26))
        addnewcategory_pushButton.setText(("Add"))
        addnewcategory_pushButton.setObjectName(("addnewcategory_pushButton"))

        deletecategory_groupBox = QtGui.QGroupBox(categories_dialog)
        deletecategory_groupBox.setGeometry(QtCore.QRect(10, 110, 321, 51))
        deletecategory_groupBox.setTitle(("Delete category"))
        deletecategory_groupBox.setObjectName(("deletecategory_groupBox"))

        self.selectcategory_comboBox = QtGui.QComboBox(deletecategory_groupBox)
        self.selectcategory_comboBox.setGeometry(QtCore.QRect(10, 20, 231, 22))
        self.selectcategory_comboBox.setObjectName(("selectcategory_comboBox"))

        self.selectcategory_comboBox.addItems(self.manager._categories)

        deletecategory_pushButton = QtGui.QPushButton(deletecategory_groupBox)
        deletecategory_pushButton.setGeometry(QtCore.QRect(250, 20, 61, 21))
        deletecategory_pushButton.setText(("Delete"))
        deletecategory_pushButton.setObjectName(("deletecategory_pushButton"))


        def onAddCategory():
            self.manager.addCategory(self.categoryName_lineEdit.text())


            preTab = QtGui.QWidget()
            preTab.setObjectName(self.categoryName_lineEdit.text())
            self.category_tabWidget.addTab(preTab, self.categoryName_lineEdit.text())
            self.selectcategory_comboBox.addItem(self.categoryName_lineEdit.text())

            self.categoryName_lineEdit.setText("")

        def onRemoveCategory():
            self.manager.removeCategory(self.selectcategory_comboBox.currentText())
            self.selectcategory_comboBox.clear()
            self.selectcategory_comboBox.addItems(self.manager.getCategories())

            self._initCategories()


        addnewcategory_pushButton.clicked.connect(onAddCategory)
        deletecategory_pushButton.clicked.connect(onRemoveCategory)

        self.categoryName_lineEdit.textChanged.connect(
            lambda: self._checkValidity(self.categoryName_lineEdit.text(), addnewcategory_pushButton,
                                        self.categoryName_lineEdit))


        categories_dialog.show()

    def projectSettingsUI(self):
        admin_pswd = "682"
        passw, ok = QtGui.QInputDialog.getText(self, "Password Query", "Enter Admin Password:",
                                                   QtGui.QLineEdit.Password)
        if ok:
            if passw == admin_pswd:
                pass
            else:
                self.infoPop(textTitle="Incorrect Password", textHeader="The Password is invalid")
                return
        else:
            return

        projectSettingsDB = self.masterManager._loadProjectSettings()

        projectSettings_Dialog = QtGui.QDialog(parent=self)
        projectSettings_Dialog.setObjectName("projectSettings_Dialog")
        projectSettings_Dialog.resize(270, 120)
        projectSettings_Dialog.setMinimumSize(QtCore.QSize(270, 120))
        projectSettings_Dialog.setMaximumSize(QtCore.QSize(270, 120))
        projectSettings_Dialog.setWindowTitle("Project Settings")

        gridLayout = QtGui.QGridLayout(projectSettings_Dialog)
        gridLayout.setObjectName(("gridLayout"))

        buttonBox = QtGui.QDialogButtonBox(projectSettings_Dialog)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        buttonBox.setMaximumSize(QtCore.QSize(16777215, 30))
        buttonBox.setOrientation(QtCore.Qt.Horizontal)
        buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Cancel | QtGui.QDialogButtonBox.Save)
        buttonBox.setObjectName("buttonBox")

        gridLayout.addWidget(buttonBox, 1, 0, 1, 1)

        formLayout = QtGui.QFormLayout()
        formLayout.setFieldGrowthPolicy(QtGui.QFormLayout.AllNonFixedFieldsGrow)
        formLayout.setLabelAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing | QtCore.Qt.AlignVCenter)
        formLayout.setFormAlignment(QtCore.Qt.AlignLeading | QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        formLayout.setObjectName("formLayout")

        resolution_label = QtGui.QLabel(projectSettings_Dialog)
        resolution_label.setText("Resolution:")
        resolution_label.setObjectName("resolution_label")
        formLayout.setWidget(0, QtGui.QFormLayout.LabelRole, resolution_label)

        horizontalLayout = QtGui.QHBoxLayout()
        horizontalLayout.setObjectName("horizontalLayout")

        resolutionX_spinBox = QtGui.QSpinBox(projectSettings_Dialog)
        resolutionX_spinBox.setButtonSymbols(QtGui.QAbstractSpinBox.NoButtons)
        resolutionX_spinBox.setObjectName("resolutionX_spinBox")
        horizontalLayout.addWidget(resolutionX_spinBox)
        resolutionX_spinBox.setRange(1, 99999)
        resolutionX_spinBox.setValue(projectSettingsDB["Resolution"][0])

        resolutionY_spinBox = QtGui.QSpinBox(projectSettings_Dialog)
        resolutionY_spinBox.setButtonSymbols(QtGui.QAbstractSpinBox.NoButtons)
        resolutionY_spinBox.setObjectName("resolutionY_spinBox")
        horizontalLayout.addWidget(resolutionY_spinBox)
        resolutionY_spinBox.setRange(1, 99999)
        resolutionY_spinBox.setValue(projectSettingsDB["Resolution"][1])

        formLayout.setLayout(0, QtGui.QFormLayout.FieldRole, horizontalLayout)
        fps_label = QtGui.QLabel(projectSettings_Dialog)
        fps_label.setText("FPS")
        fps_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing | QtCore.Qt.AlignVCenter)
        fps_label.setObjectName("fps_label")
        formLayout.setWidget(1, QtGui.QFormLayout.LabelRole, fps_label)

        fps_comboBox = QtGui.QComboBox(projectSettings_Dialog)
        fps_comboBox.setMaximumSize(QtCore.QSize(60, 16777215))
        fps_comboBox.setObjectName("fps_comboBox")
        formLayout.setWidget(1, QtGui.QFormLayout.FieldRole, fps_comboBox)
        fps_comboBox.addItems(self.masterManager.fpsList)
        try:
            index = self.manager.fpsList.index(str(projectSettingsDB["FPS"]))
        except:
            index = 2
        fps_comboBox.setCurrentIndex(index)
        gridLayout.addLayout(formLayout, 0, 0, 1, 1)

        # SIGNALS
        # -------
        def onAccepted():
            projectSettingsDB = {"Resolution": [resolutionX_spinBox.value(), resolutionY_spinBox.value()],
                                 "FPS": int(fps_comboBox.currentText())}
            self.masterManager._saveProjectSettings(projectSettingsDB)
            projectSettings_Dialog.close()


        buttonBox.accepted.connect(onAccepted)
        buttonBox.rejected.connect(projectSettings_Dialog.reject)

        projectSettings_Dialog.show()

    def saveBaseSceneDialog(self):
        self.save_Dialog = QtGui.QDialog(parent=self)
        self.save_Dialog.setModal(True)
        self.save_Dialog.setObjectName(("save_Dialog"))
        self.save_Dialog.resize(500, 240)
        self.save_Dialog.setMinimumSize(QtCore.QSize(500, 240))
        self.save_Dialog.setMaximumSize(QtCore.QSize(500, 240))
        self.save_Dialog.setWindowTitle(("Save New Base Scene"))

        self.sdNotes_label = QtGui.QLabel(self.save_Dialog)
        self.sdNotes_label.setGeometry(QtCore.QRect(260, 15, 61, 20))
        self.sdNotes_label.setText(("Notes"))
        self.sdNotes_label.setObjectName(("sdNotes_label"))

        self.sdNotes_textEdit = QtGui.QTextEdit(self.save_Dialog)
        self.sdNotes_textEdit.setGeometry(QtCore.QRect(260, 40, 215, 180))
        self.sdNotes_textEdit.setObjectName(("sdNotes_textEdit"))

        self.sdSubP_label = QtGui.QLabel(self.save_Dialog)
        self.sdSubP_label.setGeometry(QtCore.QRect(20, 30, 61, 20))
        self.sdSubP_label.setFrameShape(QtGui.QFrame.Box)
        self.sdSubP_label.setText(("Sub-Project"))
        self.sdSubP_label.setObjectName(("sdSubP_label"))

        self.sdSubP_comboBox = QtGui.QComboBox(self.save_Dialog)
        self.sdSubP_comboBox.setFocus()
        self.sdSubP_comboBox.setGeometry(QtCore.QRect(90, 30, 151, 22))
        self.sdSubP_comboBox.setObjectName(("sdCategory_comboBox"))
        self.sdSubP_comboBox.addItems((self.manager._subProjectsList))
        self.sdSubP_comboBox.setCurrentIndex(self.subProject_comboBox.currentIndex())

        self.sdName_label = QtGui.QLabel(self.save_Dialog)
        self.sdName_label.setGeometry(QtCore.QRect(20, 70, 61, 20))
        self.sdName_label.setFrameShape(QtGui.QFrame.Box)
        self.sdName_label.setText(("Name"))
        self.sdName_label.setObjectName(("sdName_label"))

        self.sdName_lineEdit = QtGui.QLineEdit(self.save_Dialog)
        self.sdName_lineEdit.setGeometry(QtCore.QRect(90, 70, 151, 20))
        self.sdName_lineEdit.setCursorPosition(0)
        self.sdName_lineEdit.setPlaceholderText(("Choose an unique name"))
        self.sdName_lineEdit.setObjectName(("sdName_lineEdit"))

        self.sdCategory_label = QtGui.QLabel(self.save_Dialog)
        self.sdCategory_label.setGeometry(QtCore.QRect(20, 110, 61, 20))
        self.sdCategory_label.setFrameShape(QtGui.QFrame.Box)
        self.sdCategory_label.setText(("Category"))
        self.sdCategory_label.setObjectName(("sdCategory_label"))

        self.sdCategory_comboBox = QtGui.QComboBox(self.save_Dialog)
        self.sdCategory_comboBox.setFocus()
        self.sdCategory_comboBox.setGeometry(QtCore.QRect(90, 110, 151, 22))
        self.sdCategory_comboBox.setObjectName(("sdCategory_comboBox"))
        for i in range(len(self.manager._categories)):
            self.sdCategory_comboBox.addItem((self.manager._categories[i]))
            self.sdCategory_comboBox.setItemText(i, (self.manager._categories[i]))
        self.sdCategory_comboBox.setCurrentIndex(self.category_tabWidget.currentIndex())

        self.sdMakeReference_checkbox = QtGui.QCheckBox("Make it Reference", self.save_Dialog)
        self.sdMakeReference_checkbox.setGeometry(QtCore.QRect(130, 150, 151, 22))

        self.sd_buttonBox = QtGui.QDialogButtonBox(self.save_Dialog)
        self.sd_buttonBox.setGeometry(QtCore.QRect(20, 190, 220, 32))
        self.sd_buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.sd_buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel)
        self.sd_buttonBox.setObjectName(("sd_buttonBox"))

        def saveCommand():
            checklist = self.manager.preSaveChecklist()
            for msg in checklist:
                q = self.queryPop(type="yesNo", textTitle="Checklist", textHeader=msg)
                if q == "no":
                    return
                else:
                    self.manager.errorLogger(title="Disregarded warning", errorMessage=msg)

            category = self.sdCategory_comboBox.currentText()
            name = self.sdName_lineEdit.text()
            subIndex = self.sdSubP_comboBox.currentIndex()
            makeReference = self.sdMakeReference_checkbox.checkState()
            notes = self.sdNotes_textEdit.toPlainText()
            sceneFormat = "max"
            self.manager.saveBaseScene(category, name, subIndex, makeReference, notes, sceneFormat)
            self.populateBaseScenes()
            self.manager.getOpenSceneInfo()
            self._initOpenScene()
            self.save_Dialog.accept()

        # SIGNALS
        # -------
        self.sdName_lineEdit.textChanged.connect(
            lambda: self._checkValidity(self.sdName_lineEdit.text(), self.sd_buttonBox, self.sdName_lineEdit))

        self.sd_buttonBox.accepted.connect(saveCommand)


        # self.sd_buttonBox.accepted.connect(self.save_Dialog.accept)
        self.sd_buttonBox.rejected.connect(self.save_Dialog.reject)
        # QtCore.QMetaObject.connectSlotsByName(self.save_Dialog)

        self.save_Dialog.show()

    def saveAsVersionDialog(self):
        saveV_Dialog = QtGui.QDialog(parent=self)
        saveV_Dialog.setModal(True)
        saveV_Dialog.setObjectName(("saveV_Dialog"))
        saveV_Dialog.resize(255, 290)
        saveV_Dialog.setMinimumSize(QtCore.QSize(255, 290))
        saveV_Dialog.setMaximumSize(QtCore.QSize(255, 290))
        saveV_Dialog.setWindowTitle(("Save As Version"))

        svNotes_label = QtGui.QLabel(saveV_Dialog)
        svNotes_label.setGeometry(QtCore.QRect(15, 15, 61, 20))
        svNotes_label.setText(("Version Notes"))
        svNotes_label.setObjectName(("sdNotes_label"))

        self.svNotes_textEdit = QtGui.QTextEdit(saveV_Dialog)
        self.svNotes_textEdit.setGeometry(QtCore.QRect(15, 40, 215, 170))
        self.svNotes_textEdit.setObjectName(("sdNotes_textEdit"))

        self.svMakeReference_checkbox = QtGui.QCheckBox("Make it Reference", saveV_Dialog)
        self.svMakeReference_checkbox.setGeometry(QtCore.QRect(130, 215, 151, 22))
        self.svMakeReference_checkbox.setChecked(False)

        sv_buttonBox = QtGui.QDialogButtonBox(saveV_Dialog)
        sv_buttonBox.setGeometry(QtCore.QRect(20, 250, 220, 32))
        sv_buttonBox.setOrientation(QtCore.Qt.Horizontal)
        sv_buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Save | QtGui.QDialogButtonBox.Cancel)

        buttonS = sv_buttonBox.button(QtGui.QDialogButtonBox.Save)
        buttonS.setText('Save As Version')
        buttonC = sv_buttonBox.button(QtGui.QDialogButtonBox.Cancel)
        buttonC.setText('Cancel')

        sv_buttonBox.setObjectName(("sd_buttonBox"))

        def saveAsVersionCommand():
            checklist = self.manager.preSaveChecklist()
            for msg in checklist:
                q = self.queryPop(type="yesNo", textTitle="Checklist", textHeader=msg)
                if q == "no":
                    return
                else:
                    self.manager.errorLogger(title = "Disregarded warning" , errorMessage=msg)

            sceneInfo = self.manager.saveVersion(makeReference=self.svMakeReference_checkbox.checkState(),
                                     versionNotes=self.svNotes_textEdit.toPlainText())

            if not sceneInfo == -1:
                self.statusBar().showMessage("Status | Version Saved => %s" % len(sceneInfo["Versions"]))
            self.manager.currentBaseSceneName = sceneInfo["Name"]
            self.manager.currentVersionIndex = len(sceneInfo["Versions"])

            currentRow = self.scenes_listWidget.currentRow()
            self.populateBaseScenes()
            self.onBaseSceneChange()
            self.scenes_listWidget.setCurrentRow(currentRow)
            # self.populateBaseScenes()
            saveV_Dialog.accept()

        # SIGNALS
        # -------
        sv_buttonBox.accepted.connect(saveAsVersionCommand)
        # sv_buttonBox.accepted.connect(saveV_Dialog.accept)
        sv_buttonBox.rejected.connect(saveV_Dialog.reject)
        # QtCore.QMetaObject.connectSlotsByName(saveV_Dialog)

        sceneInfo = self.manager.getOpenSceneInfo()
        if sceneInfo:
            saveV_Dialog.show()
        else:
            self.infoPop(textInfo="Version Saving not possible",
                         textHeader="Current Scene is not a Base Scene. Only versions of Base Scenes can be saved", textTitle="Not a Base File", type="C")
            self.manager.errorLogger(title="Misuse Error", errorMessage="A version tried to be saved without base scene")

    def addNoteDialog(self):
        row = self.scenes_listWidget.currentRow()
        if row == -1:
            return

        addNotes_Dialog = QtGui.QDialog(parent=self)
        addNotes_Dialog.setModal(True)
        addNotes_Dialog.setObjectName(("addNotes_Dialog"))
        addNotes_Dialog.resize(255, 290)
        addNotes_Dialog.setMinimumSize(QtCore.QSize(255, 290))
        addNotes_Dialog.setMaximumSize(QtCore.QSize(255, 290))
        addNotes_Dialog.setWindowTitle(("Add Notes"))

        addNotes_label = QtGui.QLabel(addNotes_Dialog)
        addNotes_label.setGeometry(QtCore.QRect(15, 15, 100, 20))
        addNotes_label.setText(("Additional Notes"))
        addNotes_label.setObjectName(("addNotes_label"))

        addNotes_textEdit = QtGui.QTextEdit(addNotes_Dialog)
        addNotes_textEdit.setGeometry(QtCore.QRect(15, 40, 215, 170))
        addNotes_textEdit.setObjectName(("addNotes_textEdit"))

        addNotes_buttonBox = QtGui.QDialogButtonBox(addNotes_Dialog)
        addNotes_buttonBox.setGeometry(QtCore.QRect(20, 250, 220, 32))
        addNotes_buttonBox.setOrientation(QtCore.Qt.Horizontal)
        addNotes_buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Save | QtGui.QDialogButtonBox.Cancel)

        buttonS = addNotes_buttonBox.button(QtGui.QDialogButtonBox.Save)
        buttonS.setText('Add Notes')
        buttonC = addNotes_buttonBox.button(QtGui.QDialogButtonBox.Cancel)
        buttonC.setText('Cancel')

        addNotes_buttonBox.setObjectName(("addNotes_buttonBox"))
        addNotes_buttonBox.accepted.connect(lambda: self.manager.addNote(addNotes_textEdit.toPlainText()))
        addNotes_buttonBox.accepted.connect(self.onVersionChange)
        addNotes_buttonBox.accepted.connect(addNotes_Dialog.accept)

        addNotes_buttonBox.rejected.connect(addNotes_Dialog.reject)
        QtCore.QMetaObject.connectSlotsByName(addNotes_Dialog)

        addNotes_Dialog.show()

    # TODO : PROJECT SETTINGS UI

    def initMainUI(self, newborn=False):

        if not newborn:
            self.manager.init_paths()
            self.manager.init_database()

        self._initCategories()

        self.manager.getOpenSceneInfo()

        self._initOpenScene()

        # init project
        self.project_lineEdit.setText(self.manager.projectDir)

        # init subproject
        self._initSubProjects()

        # init base scenes
        self.populateBaseScenes()

        # init users
        self._initUsers()

        # disable the version related stuff
        self.version_comboBox.setStyleSheet("background-color: rgb(80,80,80); color: white")
        self._vEnableDisable()

    def refresh(self):
        # currentUserIndex = self.user_comboBox.currentIndex()
        # currentTabIndex = self
        self.initMainUI()

        self.populateBaseScenes()

    def rcAction_scenes(self, command):
        if command == "importScene":
            self.manager.importBaseScene()

        if command == "showInExplorerMaya":
            self.manager.showInExplorer(self.manager.currentBaseScenePath)

        if command == "showInExplorerPB":
            self.manager.showInExplorer(self.manager.currentPreviewPath)

        if command == "showInExplorerData":
            filePath = self.manager._baseScenesInCategory[self.manager.currentBaseSceneName]
            dirPath = os.path.dirname(filePath)
            self.manager.showInExplorer(dirPath)

        if command == "showSceneInfo":
            textInfo = pprint.pformat(self.manager._currentSceneInfo)
            print self.manager._currentSceneInfo
            self.messageDialog = QtGui.QDialog()
            self.messageDialog.setWindowTitle("Scene Info")
            self.messageDialog.resize(800, 700)
            self.messageDialog.show()
            messageLayout = QtGui.QVBoxLayout(self.messageDialog)
            messageLayout.setContentsMargins(0, 0, 0, 0)
            helpText = QtGui.QTextEdit()
            helpText.setReadOnly(True)
            helpText.setStyleSheet("background-color: rgb(255, 255, 255);")
            helpText.setStyleSheet(""
                                   "border: 20px solid black;"
                                   "background-color: black;"
                                   "font-size: 16px"
                                   "")
            helpText.setText(textInfo)
            messageLayout.addWidget(helpText)

    def rcAction_thumb(self, command):
        # print "comm: ", command
        if command == "file":
            fname = QtGui.QFileDialog.getOpenFileName(self, 'Open file', self.manager.projectDir,"Image files (*.jpg *.gif)")[0]
            if not fname: # if dialog is canceled
                return

        elif command == "currentView":
            fname = ""

        else:
            return

        self.manager.replaceThumbnail(filePath=fname)
        self.onVersionChange()

    def onContextMenu_scenes(self, point):
        row = self.scenes_listWidget.currentRow()
        if row == -1:
            return
        # check paths
        self.scenes_rcItem_1.setEnabled(os.path.isdir(self.manager.currentBaseScenePath))
        self.scenes_rcItem_2.setEnabled(os.path.isdir(self.manager.currentPreviewPath))
        # show context menu
        self.popMenu_scenes.exec_(self.scenes_listWidget.mapToGlobal(point))
    def onContextMenu_thumbnail(self, point):
        row = self.scenes_listWidget.currentRow()
        if row == -1:
            return
        # show context menu
        self.popMenu_thumbnail.exec_(self.thumbnail_label.mapToGlobal(point))

    def onProjectChange(self):
        self.initMainUI()
        # self.onSubProjectChange()
        # self.onCategoryChange()
        # self.onBaseSceneChange()
        # self.onVersionChange()
        # self.onPreviewChange()

    def onSubProjectChange(self):
        self.manager.currentSubIndex = self.subProject_comboBox.currentIndex()
        self.onCategoryChange()

    def onCategoryChange(self):
        self.manager.currentTabIndex = self.category_tabWidget.currentIndex()
        self.populateBaseScenes()
        self.onBaseSceneChange()

    def onUserChange(self):
        self.manager.currentUser = self.user_comboBox.currentText()
        print self.manager.currentUser

    def onModeChange(self):

        self._vEnableDisable()

        if self.load_radioButton.isChecked():
            self.loadScene_pushButton.setText("Load Scene")
            self.scenes_listWidget.setStyleSheet("border-style: solid; border-width: 2px; border-color: grey;")
        else:
            self.loadScene_pushButton.setText("Reference Scene")
            self.scenes_listWidget.setStyleSheet("border-style: solid; border-width: 2px; border-color: cyan;")

        self.manager.currentMode = self.load_radioButton.isChecked()
        self.populateBaseScenes()

    def onBaseSceneChange(self):
        self.version_comboBox.blockSignals(True)

        #clear version_combobox
        self.version_comboBox.clear()

        row = self.scenes_listWidget.currentRow()
        if row == -1:
            self.manager.currentBaseSceneName = ""

        else:
            self.manager.currentBaseSceneName = self.scenes_listWidget.currentItem().text()

        self._vEnableDisable()
        #get versions and add it to the combobox
        versionData = self.manager.getVersions()
        for num in range(len(versionData)):
            self.version_comboBox.addItem("v{0}".format(str(num + 1).zfill(3)))
        self.version_comboBox.setCurrentIndex(self.manager.currentVersionIndex-1)
        self.onVersionChange()

        self.version_comboBox.blockSignals(False)

    def onVersionChange(self):

        self.version_comboBox.blockSignals(True)

        if self.version_comboBox.currentIndex() is not -1:
            self.manager.currentVersionIndex = self.version_comboBox.currentIndex() + 1

        # clear Notes and verison combobox
        self.notes_textEdit.clear()

        # update notes
        self.notes_textEdit.setPlainText(self.manager.getNotes())

        # update thumb
        self.tPixmap = QtGui.QPixmap(self.manager.getThumbnail())
        self.thumbnail_label.setPixmap(self.tPixmap)

        if self.manager.currentVersionIndex != len(self.manager.getVersions()) and self.manager.currentVersionIndex != -1:
            self.version_comboBox.setStyleSheet("background-color: rgb(80,80,80); color: yellow")
        else:
            self.version_comboBox.setStyleSheet("background-color: rgb(80,80,80); color: white")

        self.version_comboBox.blockSignals(False)

    def populateBaseScenes(self, deepCheck=False):
        self.scenes_listWidget.blockSignals(True)

        self.scenes_listWidget.clear()
        baseScenesDict = self.manager.getBaseScenesInCategory()
        if self.reference_radioButton.isChecked():
            for key in baseScenesDict:
                if self.manager.checkReference(baseScenesDict[key]) == 1:
                    self.scenes_listWidget.addItem(key)

        else:
            codeDict = {-1: QtGui.QColor(255, 0, 0, 255), 1: QtGui.QColor(0, 255, 0, 255),
                        0: QtGui.QColor(255, 255, 0, 255), -2: QtGui.QColor(20, 20, 20, 255)}  # dictionary for color codes red, green, yellow
                        # gray for the corrupted database file

            for key in sorted(baseScenesDict):
                retCode = self.manager.checkReference(baseScenesDict[key], deepCheck=deepCheck) # returns -1, 0, 1 or -2 for color ref
                color = codeDict[retCode]
                listItem = QtGui.QListWidgetItem()
                listItem.setText(key)
                listItem.setForeground(color)
                self.scenes_listWidget.addItem(listItem)
        self.scenes_listWidget.blockSignals(False)

    def onLoadScene(self):
        row = self.scenes_listWidget.currentRow()
        if row == -1:
            return

        res, msg = self.manager.compareVersions()
        if res == -1:
            mismatch = self.queryPop(type="yesNo", textTitle="Version Mismatch", textHeader=msg)
            if mismatch == "no":
                return
            else:
                self.manager.errorLogger(title="Disregarded warning", errorMessage=msg)

        if self.load_radioButton.isChecked():
            if self.manager.isSceneModified():
                q = self.queryPop(type="yesNoCancel", textTitle="Save Changes", textInfo="Save Changes to",
                                  textHeader=("Scene Modified"))
                if q == "yes":
                    self.manager.saveSimple()
                    self.manager.loadBaseScene(force=True)
                if q == "no":
                    self.manager.loadBaseScene(force=True)
                if q == "cancel":
                    pass


            else: # if current scene saved and secure
                self.manager.loadBaseScene(force=True)
                self.manager.getOpenSceneInfo()
                self._initOpenScene()

            self.statusBar().showMessage("Status | Scene Loaded => %s" % self.manager.currentBaseSceneName)

        if self.reference_radioButton.isChecked():
            self.manager.referenceBaseScene()
            # self.populateScenes()
            self.statusBar().showMessage("Status | Scene Referenced => %s" % self.manager.currentBaseSceneName)

    def onMakeReference(self):
        self.manager.makeReference()
        self.onVersionChange()
        self.statusBar().showMessage(
            "Status | Version {1} is the new reference of {0}".format(self.manager.currentBaseSceneName, self.manager.currentVersionIndex))
        currentRow = self.scenes_listWidget.currentRow()
        self.populateBaseScenes()
        self.scenes_listWidget.setCurrentRow(currentRow)

    def onShowPreview(self):
        # TODO // TEST IT
        row = self.scenes_listWidget.currentRow()
        if row == -1:
            return
        cameraList = self.manager.getPreviews()
        if len(self.manager.getPreviews()) == 1:
            self.manager.playPreview(cameraList[0])
        else:
            zortMenu = QtGui.QMenu()
            for z in cameraList:
                tempAction = QtGui.QAction(z, self)
                zortMenu.addAction(tempAction)
                tempAction.triggered.connect(lambda item=z: self.manager.playPreview(item)) ## Take note about the usage of lambda "item=pbDict[z]" makes it possible using the loop

            zortMenu.exec_((QtGui.QCursor.pos()))

    def onDeleteBaseScene(self):
        name = self.manager.currentBaseSceneName
        state = self.queryPop("password", textTitle="DELETE BASE SCENE", textInfo="!!!DELETING BASE SCENE!!! %s\n\nAre you absolutely sure?" %name, password="682")
        if state:
            row = self.scenes_listWidget.currentRow()
            if not row == -1:
                self.manager.deleteBasescene(self.manager.currentDatabasePath)
                self.populateBaseScenes()
                self.statusBar().showMessage("Status | Scene Deleted => %s" % name)


    def onDeleteReference(self):
        name = self.manager.currentBaseSceneName
        state = self.queryPop("password", textTitle="DELETE REFERENCE FILE", textInfo="DELETING Reference File of %s\n\nAre you sure?" %name, password="682")
        if state:
            row = self.scenes_listWidget.currentRow()
            if not row == -1:
                self.manager.deleteReference(self.manager.currentDatabasePath)
                self.populateBaseScenes()
                self.statusBar().showMessage("Status | Reference of %s is deleted" % name)

    def onImanager(self):
        # if self.isCallback:
        #     callback = "%s.imageManagerINS" %(self.isCallback)
        # else:
        #     callback = None
        #
        # self.imageManagerINS = ImMaya.MainUI(callback=callback)
        logger.warning("Image Manager N/A")
        # e = ImMaya.MainUI()

    def onIviewer(self):
        logger.warning("Image Viewer N/A")
        # IvMaya.MainUI().show()

    def _initSubProjects(self):

        self.subProject_comboBox.blockSignals(True)

        self.subProject_comboBox.clear()
        self.subProject_comboBox.addItems(self.manager.getSubProjects())
        self.subProject_comboBox.setCurrentIndex(self.manager.currentSubIndex)

        self.subProject_comboBox.blockSignals(False)

    def _initCategories(self):
        self.category_tabWidget.blockSignals(True)
        self.category_tabWidget.clear()

        for i in self.manager._categories:
            self.preTab = QtGui.QWidget()
            self.preTab.setObjectName((i))
            self.category_tabWidget.addTab(self.preTab, (i))

        self.category_tabWidget.setCurrentIndex(self.manager.currentTabIndex)
        self.category_tabWidget.blockSignals(False)

    def _initUsers(self):
        self.user_comboBox.blockSignals(True)

        # init users
        self.user_comboBox.clear()
        self.user_comboBox.addItems(self.manager.getUsers())
        index = self.user_comboBox.findText(self.manager.currentUser, QtCore.Qt.MatchFixedString)
        if index >= 0:
            self.user_comboBox.setCurrentIndex(index)

        self.user_comboBox.blockSignals(False)


    def _initOpenScene(self):
        openSceneInfo = self.manager._openSceneInfo
        logger.debug(openSceneInfo)
        # if not openSceneInfo:
        #     openSceneInfo = self.manager.getOpenSceneInfo()
        if openSceneInfo: ## getSceneInfo returns None if there is no json database fil
            self.baseScene_lineEdit.setText("%s ==> %s ==> %s" % (openSceneInfo["subProject"], openSceneInfo["category"], openSceneInfo["shotName"]))
            self.baseScene_lineEdit.setStyleSheet("background-color: rgb(40,40,40); color: cyan")
        else:
            self.baseScene_lineEdit.setText("Current Scene is not a Base Scene")
            self.baseScene_lineEdit.setStyleSheet("background-color: rgb(40,40,40); color: yellow")

    def _checkValidity(self, text, button, lineEdit, allowSpaces=False):
        if self.manager._nameCheck(text, allowSpaces=allowSpaces):
            lineEdit.setStyleSheet("background-color: rgb(40,40,40); color: white")
            button.setEnabled(True)
        else:
            lineEdit.setStyleSheet("background-color: red; color: black")
            button.setEnabled(False)

    def _vEnableDisable(self):
        if self.load_radioButton.isChecked() and self.manager.currentBaseSceneName:
            self.version_comboBox.setEnabled(True)
            if self.manager.getPreviews():
                self.showPreview_pushButton.setEnabled(True)
            else:
                self.showPreview_pushButton.setEnabled(False)
            self.makeReference_pushButton.setEnabled(True)
            self.addNote_pushButton.setEnabled(True)
            self.version_label.setEnabled(True)

        else:
            self.version_comboBox.setEnabled(False)
            self.showPreview_pushButton.setEnabled(False)
            self.makeReference_pushButton.setEnabled(False)
            self.addNote_pushButton.setEnabled(False)
            self.version_label.setEnabled(False)


    def infoPop(self, textTitle="info", textHeader="", textInfo="", type="I"):
        self.msg = QtGui.QMessageBox(parent=self)
        if type == "I":
            self.msg.setIcon(QtGui.QMessageBox.Information)
        if type == "C":
            self.msg.setIcon(QtGui.QMessageBox.Critical)

        self.msg.setText(textHeader)
        self.msg.setInformativeText(textInfo)
        self.msg.setWindowTitle(textTitle)
        self.msg.setStandardButtons(QtGui.QMessageBox.Ok)
        self.msg.show()

    def queryPop(self, type, textTitle="Question", textHeader="", textInfo="", password=""):
        if type == "password":
            if password != "":
                passw, ok= QtGui.QInputDialog.getText(self, textTitle,
                                                       textInfo, QtGui.QLineEdit.Password, parent=self)
                if ok:
                    if passw == password:
                        return True
                    else:
                        self.infoPop(textTitle="Incorrect Passsword", textHeader="Incorrect Password", type="C")
                        return False
                else:
                    return False
            else:
                return -1

        if type == "yesNoCancel":

            q = QtGui.QMessageBox(parent=self)
            q.setIcon(QtGui.QMessageBox.Question)
            q.setText(textHeader)
            q.setInformativeText(textInfo)
            q.setWindowTitle(textTitle)
            q.setStandardButtons(
                QtGui.QMessageBox.Save | QtGui.QMessageBox.No | QtGui.QMessageBox.Cancel)
            ret = q.exec_()
            if ret == QtGui.QMessageBox.Save:
                return "yes"
            elif ret == QtGui.QMessageBox.No:
                return "no"
            elif ret == QtGui.QMessageBox.Cancel:
                return "cancel"

        if type == "okCancel":
            q = QtGui.QMessageBox(parent=self)
            q.setIcon(QtGui.QMessageBox.Question)
            q.setText(textHeader)
            q.setInformativeText(textInfo)
            q.setWindowTitle(textTitle)
            q.setStandardButtons(QtGui.QMessageBox.Ok | QtGui.QMessageBox.Cancel)
            ret = q.exec_()
            if ret == QtGui.QMessageBox.Ok:
                return "ok"
            elif ret == QtGui.QMessageBox.Cancel:
                return "cancel"

        if type == "yesNo":
            q = QtGui.QMessageBox(parent=self)
            q.setIcon(QtGui.QMessageBox.Question)
            q.setText(textHeader)
            q.setInformativeText(textInfo)
            q.setWindowTitle(textTitle)
            q.setStandardButtons(QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
            ret = q.exec_()
            if ret == QtGui.QMessageBox.Yes:
                return "yes"
            elif ret == QtGui.QMessageBox.No:
                return "no"



class ImageWidget(QtGui.QLabel):
    """Custom class for thumbnail section. Keeps the aspect ratio when resized."""
    def __init__(self, parent=None):
        super(ImageWidget, self).__init__()
        self.aspectRatio = 1.78
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHeightForWidth(True)
        self.setSizePolicy(sizePolicy)

    def resizeEvent(self, r):
        h = self.width()
        self.setMinimumHeight(h/self.aspectRatio)
        self.setMaximumHeight(h/self.aspectRatio)

class DropListWidget(QtGui.QListWidget):
    """Custom List Widget which accepts drops"""
    # dropped = Qt.QtCore.Signal(str)
    dropped = QtCore.Signal(str)
    def __init__(self, type, parent=None):
        super(DropListWidget, self).__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat('text/uri-list'):
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat('text/uri-list'):
            event.setDropAction(QtCore.Qt.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        rawPath = event.mimeData().data('text/uri-list').__str__()
        path = rawPath.replace("file:///", "").splitlines()[0]
        self.dropped.emit(path)

class Browse(object):
    """Browsing class with history"""
    def __init__(self):
        super(Browse, self).__init__()
        self.history = []
        self.index = 0
        self.undoCount = 10
    def forward(self):
        if not self.isForwardLocked():
            self.index += 1
        else:
            pass
    def backward(self):
        if not self.isBackwardLocked():
            self.index -= 1
        else:
            pass
    def addData(self, data):
        # if the incoming data is identical with the current, do nothing
        try:
            currentData = self.history[self.index]
            if data == currentData:
                return
        except IndexError:
            pass
        # delete history after index
        del self.history[self.index+1:]
        self.history.append(data)
        if len(self.history) > self.undoCount:
            self.history.pop(0)
        self.index = len(self.history)-1
        # the new data writes the history, so there is no future
        self.forwardLimit = True
        # but there is past
        self.backwardLimit = False
    def getData(self, index=None):
        if index:
            return self.history[index]
        else:
            return self.history[self.index]
    def isBackwardLocked(self):
        return self.index == 0
    def isForwardLocked(self):
        return self.index == (len(self.history)-1)

