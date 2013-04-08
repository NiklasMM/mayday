#!/usr/bin/env python
# -*- coding: UTF-8 -*-

# Copyright 2013
# Author: Nikolaus Mayer (cheglastgnat)


########################################################################
# TODO features
# - DONE mouse camera
# - DONE clickable game objects / how precise?
# - z-ordering (treap?)
# - DONE adding / moving objects
# - autojoining objects at ends to form a path
# - automatically close a cyclic path
# - context menu
# - undo/redo
# - while moving objects: hold CTRL to snap to grid
# - path pieces cast shadows onto the ground
# - DONE save / load sessions
# - export finished levels
#
# TODO fixes
# - observation:   boxselection + mmb/rmb -> boxselection and camera change
#                  at the same time, releasing one cancels boxselection
#   problem:       this isn't user-expected behavior
#   solution idea: while lmb dragging, ignore mmb and rmb; likewise, while
#                  mmb or rmb dragging, ignore lmb (but not mmb or rmb)
#
# TODO else
# - DONE render font objects only once
#   applicable pbjects include: debug texts, button tooltips, "toggle" text
# - comment, comment, comment, document, document, document!
#
# ONLY IN GAME
# - wind (+ graphic effects?)
# - cosmetic effects: rain, snow (particles?)
# - windfarms, birds, cars on highways
# - cloud shadows
# - level graphic sets for different daytimes, weather conditions
# - graphic sets change with the daytime
########################################################################

import pygame
from math import pi, sin, cos
import logging, sys, os, pickle, shelve
from collections import deque

# import pygtk
import gtk
# pygtk.require('2.0')

SCRIPT_PATH = os.path.dirname(__file__)

WINDOW_SIZE = [800, 600]
ORIGIN = [WINDOW_SIZE[0]//2, WINDOW_SIZE[1]//2]
AZIMUTH_ANGULAR_SPEED = 0.05
ELEVATION_ANGULAR_SPEED = 0.05
ZOOM_IN_SPEED = 1.05
ZOOM_OUT_SPEED = 0.95
MOUSE_AZIMUTH_ANGULAR_SPEED = 0.1
MOUSE_ELEVATION_ANGULAR_SPEED = 0.1
MOUSE_ZOOM_IN_SPEED = 0.1
MOUSE_ZOOM_OUT_SPEED = 0.1

# Don't have to hold the mouse perfectly still for "clicks" (vs dragging)
DRAGGING_DISTANCE_THRESHOLD = 5

# Camera parameters
azimuth = 315.*(pi/180.)
elevation = -66.*(pi/180.)
# Parts of the orthogonal projection matrix
right = [cos(azimuth), sin(azimuth) * cos(elevation)]
front = [sin(azimuth), -cos(azimuth) * cos(elevation)]
up = [0, sin(elevation)]
zoom = 1.

# Objects register clicks even if the object was not hit with pixel precision.
# Instead, all pixels within a disk around the cursor are checked.
# WARNING: Do not set this radius to 0!
CLICK_TOLERANCE_RADIUS  = 5
CLICK_TOLERANCE_OFFSETS = []
MARK_RING_OFFSETS = []
MARK_DOT_OFFSETS = []
for y in range(-CLICK_TOLERANCE_RADIUS,CLICK_TOLERANCE_RADIUS+1):
  for x in range(-CLICK_TOLERANCE_RADIUS,CLICK_TOLERANCE_RADIUS+1):
    if x**2+y**2 <= CLICK_TOLERANCE_RADIUS**2+1:
      CLICK_TOLERANCE_OFFSETS.append((x, y))
    if CLICK_TOLERANCE_RADIUS**2-8 <= x**2+y**2 <= CLICK_TOLERANCE_RADIUS**2+1:
      MARK_RING_OFFSETS.append((x, y))
    if x**2+y**2 <= CLICK_TOLERANCE_RADIUS**2-16:
      MARK_DOT_OFFSETS.append((x,y))

markring = pygame.Surface((2*CLICK_TOLERANCE_RADIUS+1,
                           2*CLICK_TOLERANCE_RADIUS+1))
markdot  = pygame.Surface((2*CLICK_TOLERANCE_RADIUS+1,
                           2*CLICK_TOLERANCE_RADIUS+1))
markrectangle = pygame.Surface((2*CLICK_TOLERANCE_RADIUS+1,
                                2*CLICK_TOLERANCE_RADIUS+1))

# A list of all on-screen objects (including buttons!)
objectsList = []
# The currently selected objects
selectedObjects = []
# Holds the strings added by infoMessage(), read by drawHelpDebugInfoMessages()
messageQueue = deque()
messageQueueChange = False

# Operation histories
# Trivial and inefficient implementation: The entire scene status is logged...
undoHistory = deque()
redoHistory = deque()

# Tells if a click was "doing nothing" (click into empty space)
idleClick = True


TOOLTIP_TEXTS = {
                 "dummy":
                  "<<<TOOLTIP_TEXTS[CLASS_NAME_AS_STRING]>>>",
                 "AddStraightButton":
                  "Add a straight path piece",
                 "AppendStraightButton":
                  "Append a straight path piece to a selected path piece",
                 "AddHelixArcButton":
                  "Add a curved path piece",
                 "AppendHelixArcButton":
                  "Append a curved path piece to a selected path piece",
                 "ChangeActiveEndButton":
                  "Switch between the active ends of a path piece",
                 "DeleteObjectsButton":
                  "Permanently delete all selected objects",
                 "LoadSceneButton":
                  "Load an existing scene from disk (unsaved changes will be lost!)",
                 "SaveSceneButton":
                  "Save the current scene to disk",
                 "NewSceneButton":
                  "Create a new, blank scene (unsaved changes will be lost!)",
                 "ExitProgramButton":
                  "Exit the program (unsaved changes will be lost!)",
                 "UndoButton":
                  "Undo the last operation",
                 "RedoButton":
                  "Repeat the last undone operation"
                }
TOOLTIP_SURFACEOBJECTS = {}

#_______________________________________________________________________


class Point3D(object):
  def __init__(self, _x=0., _y=0., _z=0.):
    """Constructor"""
    self.x, self.y, self.z = _x, _y, _z

  @classmethod
  def copy(self, other):
    """Copy 'constructor'"""
    if not isinstance(other, Point3D):
      raise TypeError
    return Point3D(other.x, other.y, other.z)

  def __add__(self, other):
    """self + other"""
    if not isinstance(other, Point3D):
      raise TypeError
    return Point3D(self.x + other.x,
                   self.y + other.y,
                   self.z + other.z)

  def __sub__(self, other):
    """self - other"""
    if not isinstance(other, Point3D):
      raise TypeError
    return Point3D(self.x - other.x,
                   self.y - other.y,
                   self.z - other.z)

  def __iadd__(self, other):
    """self += other"""
    if not isinstance(other, Point3D):
      raise TypeError
    self.x += other.x
    self.y += other.y
    self.z += other.z
    return self

  def __isub__(self, other):
    """self -= other"""
    if not isinstance(other, Point3D):
      raise TypeError
    self.x -= other.x
    self.y -= other.y
    self.z -= other.z
    return self

  def __mul__(self, other):
    """self * other"""
    if not isinstance(other, (int, long, float)):
      raise TypeError
    if isinstance(other, float):
      return Point3D(self.x * other,
                     self.y * other,
                     self.z * other)
    else:
      return Point3D(self.x * float(other),
                     self.y * float(other),
                     self.z * float(other))

  def __rmul__(self, other):
    """other * self"""
    return self.__mul__(other)

  def __div__(self, other):
    """self / other"""
    if not isinstance(other, (int, long, float)):
      raise TypeError
    if isinstance(other, float):
      return Point3D(self.x / other,
                     self.y / other,
                     self.z / other)
    else:
      return Point3D(self.x / float(other),
                     self.y / float(other),
                     self.z / float(other))

  def __str__(self):
    return "(%f, %f, %f)" % (self.x, self.y, self.z)


class DisplayedObject(object):
  def __init__(self):
    self.surfaceObj = None
    self.rect = None
    self.selected = False
    # Some objects have (unique!) names
    self.name = ""
    self.center = Point3D()

  def select(self):
    self.selected = True
  def deselect(self):
    self.selected = False

  def moveTo(self, newPos):
    self.center = Point3D.copy(newPos)

  def moveByOffset(self, offset):
    self.center += offset

  def getEndPoint3d(self, getActiveEnd):
    return Point3D()

  def moveByPixelOffset(self, relativePixelMotion):
    z = self.center.z
    ppos = project3dToPixelPosition(self.center)
    ppos[0] += relativePixelMotion[0]
    ppos[1] += relativePixelMotion[1]
    self.moveTo(unprojectPixelTo3dPosition(ppos, ORIGIN, z))

  def render(self, highdefinition=False):
    return None

  def draw(self, screen):
    """
    Draw to screen
    IMPORTANT: Call self.render() before if the object's appearance depends
               on the camera pose!
    """
    self.rect.center = project3dToPixelPosition(self.center)
    screen.blit(self.surfaceObj, self.rect)


class ClickRegisteringObject(DisplayedObject):
  def __init__(self):
    super(ClickRegisteringObject, self).__init__()

  def cursorOnObject(self, mousePos=None):
    if mousePos is None:
      mousePos = pygame.mouse.get_pos()
    if not self.rect.collidepoint(mousePos):
      return False
    for x,y in CLICK_TOLERANCE_OFFSETS:
      try:
        if self.surfaceObj.get_at((mousePos[0]-self.rect.topleft[0]+x,
                                   mousePos[1]-self.rect.topleft[1]+y)) != (0,0,0,0):
          return True
      except: pass
    return False

  def inRect(self, rect):
    return rect.collidepoint(self.rect.center)


class Button(ClickRegisteringObject):
  def __init__(self, name="", buttonRect=pygame.Rect(0,0,0,0),
               buttonSurfaceObj=pygame.Surface((0,0)),
               buttonClickedSurfaceObj=pygame.Surface((0,0)),
               buttonHighlightedSurfaceObj=pygame.Surface((0,0))):
    self.name = name
    # .convert() enables surface alpha on PNG images (for "button disabled" transparency)
    self.surfaceObj = buttonSurfaceObj.convert()
    self.clickedSurfaceObj = buttonClickedSurfaceObj
    self.highlightedSurfaceObj = buttonHighlightedSurfaceObj
    self.rect = buttonRect
    # Button function activated
    self.active = False
    # Cursor on button
    self.highlighted = False
    # Button is clickable
    self.enabled = True
    # TODO call super.constructor?

  def clickAction(self):
    global idleClick
    idleClick = False
    if not self.enabled:
      infoMessage('This button is not enabled')
      raise Exception('Button %s is not enabled' % self.name)

  def setRectangle(self, newRectangle):
    self.rect = newRectangle

  def activate(self):
    if self.enabled:
      self.active = True
  def deactivate(self):
    self.active = False

  def highlight(self):
    self.highlighted = True
  def dehighlight(self):
    self.highlighted = False

  def enable(self):
    self.enabled = True
    self.surfaceObj.set_alpha(255)
  def disable(self):
    self.enabled = False
    self.surfaceObj.set_alpha(50)

  def draw(self, screen):
    if not self.enabled:
      screen.blit(self.surfaceObj, self.rect)
    elif self.active:
      screen.blit(self.clickedSurfaceObj, self.rect)
    elif self.highlighted:
      screen.blit(self.highlightedSurfaceObj, self.rect)
    else:
      screen.blit(self.surfaceObj, self.rect)

  def tooltip(self, screen, mousePos=None, key="dummy"):
    """Check cursorOnObject before calling!"""
    if mousePos is None:
      mousePos = pygame.mouse.get_pos()
    tooltipSurfaceObj = TOOLTIP_SURFACEOBJECTS[key]
    tmpTooltipTextObjRect = tooltipSurfaceObj.get_rect()
    if mousePos[0] <= WINDOW_SIZE[0]//2:
      tmpTooltipTextObjRect.topleft = (mousePos[0]+15, mousePos[1]+5)
    else:
      tmpTooltipTextObjRect.topright = (mousePos[0]-5, mousePos[1]+5)
    screen.blit(tooltipSurfaceObj, tmpTooltipTextObjRect)


class AddStraightButton(Button):
  def __init__(self, name="AddStraightButton", buttonRect=pygame.Rect(0,0,0,0),
               buttonSurfaceObj=pygame.Surface((0,0)),
               buttonClickedSurfaceObj=pygame.Surface((0,0))):
    img = pygame.image.load('{}/img/addstraight.png'.format(SCRIPT_PATH))
    clickedImg = pygame.image.load('{}/img/addstraightClicked.png'.format(SCRIPT_PATH))
    highlightedImg = pygame.image.load('{}/img/addstraightHighlighted.png'.format(SCRIPT_PATH))
    super(AddStraightButton, self).__init__(name,
                                            buttonRect,
                                            img,
                                            clickedImg,
                                            highlightedImg)

  def clickAction(self):
    # Check if the button is enabled
    try:
      super(AddStraightButton, self).clickAction()
    except:
      return None
    createUndoHistory()
    global objectsList
    objectsList.append(Straight(Point3D(-20,-20,-20),
                                Point3D(20,50,20)))
    infoMessage("Straight object added.")

  def tooltip(self, screen, mousePos=None):
    super(AddStraightButton, self).tooltip(screen, mousePos, "AddStraightButton")



class AppendStraightButton(Button):
  def __init__(self, name="AppendStraightButton",
               buttonRect=pygame.Rect(0,0,0,0),
               buttonSurfaceObj=pygame.Surface((0,0)),
               buttonClickedSurfaceObj=pygame.Surface((0,0))):
    img = pygame.image.load('{}/img/appendstraight.png'.format(SCRIPT_PATH))
    clickedImg = pygame.image.load('{}/img/appendstraightClicked.png'.format(SCRIPT_PATH))
    highlightedImg = pygame.image.load('{}/img/appendstraightHighlighted.png'.format(SCRIPT_PATH))
    super(AppendStraightButton, self).__init__(name,
                                               buttonRect,
                                               img,
                                               clickedImg,
                                               highlightedImg)

  def clickAction(self):
    # Check if the button is enabled
    try:
      super(AppendStraightButton, self).clickAction()
    except:
      return None
    createUndoHistory()
    if not selectedObjects:
      infoMessage("must select a single path piece to append (none selected)")
    elif len(selectedObjects) > 1:
      infoMessage("must select a single path piece to append (%d selected)" % len(selectedObjects))
    else:
      infoMessage("I am not doing anything =(")

  def tooltip(self, screen, mousePos=None):
    super(AppendStraightButton, self).tooltip(screen, mousePos, "AppendStraightButton")


class AddHelixArcButton(Button):
  def __init__(self, name="AddHelixArcButton", buttonRect=pygame.Rect(0,0,0,0),
               buttonSurfaceObj=pygame.Surface((0,0)),
               buttonClickedSurfaceObj=pygame.Surface((0,0))):
    img = pygame.image.load('{}/img/addhelixarc.png'.format(SCRIPT_PATH))
    clickedImg = pygame.image.load('{}/img/addhelixarcClicked.png'.format(SCRIPT_PATH))
    highlightedImg = pygame.image.load('{}/img/addhelixarcHighlighted.png'.format(SCRIPT_PATH))
    super(AddHelixArcButton, self).__init__(name,
                                            buttonRect,
                                            img,
                                            clickedImg,
                                            highlightedImg)

  def clickAction(self):
    # Check if the button is enabled
    try:
      super(AddHelixArcButton, self).clickAction()
    except:
      return None
    createUndoHistory()
    global objectsList
    objectsList.append(HelixArc())
    objectsList[-1].render(True)
    infoMessage("HelixArc object added.")

  def tooltip(self, screen, mousePos=None):
    super(AddHelixArcButton, self).tooltip(screen, mousePos, "AddHelixArcButton")


class AppendHelixArcButton(Button):
  def __init__(self, name="AppendHelixArcButton",
               buttonRect=pygame.Rect(0,0,0,0),
               buttonSurfaceObj=pygame.Surface((0,0)),
               buttonClickedSurfaceObj=pygame.Surface((0,0))):
    img = pygame.image.load('{}/img/appendhelixarc.png'.format(SCRIPT_PATH))
    clickedImg = pygame.image.load('{}/img/appendhelixarcClicked.png'.format(SCRIPT_PATH))
    highlightedImg = pygame.image.load('{}/img/appendhelixarcHighlighted.png'.format(SCRIPT_PATH))
    super(AppendHelixArcButton, self).__init__(name,
                                               buttonRect,
                                               img,
                                               clickedImg,
                                               highlightedImg)

  def clickAction(self):
    # Check if the button is enabled
    try:
      super(AppendHelixArcButton, self).clickAction()
    except:
      return None
    createUndoHistory()
    if not selectedObjects:
      infoMessage("must select a single path piece to append (none selected)")
    elif len(selectedObjects) > 1:
      infoMessage("must select a single path piece to append (%d selected)" % len(selectedObjects))
    else:
      infoMessage("I am not doing anything =(")

  def tooltip(self, screen, mousePos=None):
    super(AppendHelixArcButton, self).tooltip(screen, mousePos, "AppendHelixArcButton")


class ChangeActiveEndButton(Button):
  def __init__(self, name="ChangeActiveEndButton",
               buttonRect=pygame.Rect(0,0,0,0),
               buttonSurfaceObj=pygame.Surface((0,0)),
               buttonClickedSurfaceObj=pygame.Surface((0,0))):
    img = pygame.image.load('{}/img/changeActiveEnd.png'.format(SCRIPT_PATH))
    clickedImg = pygame.image.load('{}/img/changeActiveEndClicked.png'.format(SCRIPT_PATH))
    highlightedImg = pygame.image.load('{}/img/changeActiveEndHighlighted.png'.format(SCRIPT_PATH))
    super(ChangeActiveEndButton, self).__init__(name,
                                                buttonRect,
                                                img,
                                                clickedImg,
                                                highlightedImg)

  def clickAction(self):
    # Check if the button is enabled
    try:
      super(ChangeActiveEndButton, self).clickAction()
    except:
      return None
    so = selectedObjects[0]
    so.activeEnd = 1 - so.activeEnd
    if isinstance(so, HelixArc):
      so.render(True)
    else:
      so.render()

  def tooltip(self, screen, mousePos=None):
    super(ChangeActiveEndButton, self).tooltip(screen, mousePos, "ChangeActiveEndButton")


class DeleteObjectsButton(Button):
  def __init__(self, name="DeleteObjectsButton",
               buttonRect=pygame.Rect(0,0,0,0),
               buttonSurfaceObj=pygame.Surface((0,0)),
               buttonClickedSurfaceObj=pygame.Surface((0,0))):
    img = pygame.image.load('{}/img/deleteobjects.png'.format(SCRIPT_PATH))
    clickedImg = pygame.image.load('{}/img/deleteobjectsClicked.png'.format(SCRIPT_PATH))
    highlightedImg = pygame.image.load('{}/img/deleteobjectsHighlighted.png'.format(SCRIPT_PATH))
    super(DeleteObjectsButton, self).__init__(name,
                                              buttonRect,
                                              img,
                                              clickedImg,
                                              highlightedImg)

  def clickAction(self, override=False):
    # Check if the button is enabled
    if not override:
      try:
        super(DeleteObjectsButton, self).clickAction()
      except:
        return None
    createUndoHistory()
    if selectedObjects:
      while selectedObjects:
        deleteObject(selectedObjects[-1])

  def tooltip(self, screen, mousePos=None):
    super(DeleteObjectsButton, self).tooltip(screen, mousePos, "DeleteObjectsButton")



class NewSceneButton(Button):
  def __init__(self, name="NewSceneButton",
               buttonRect=pygame.Rect(0,0,0,0),
               buttonSurfaceObj=pygame.Surface((0,0)),
               buttonClickedSurfaceObj=pygame.Surface((0,0))):
    img = pygame.image.load('{}/img/newScene.png'.format(SCRIPT_PATH))
    clickedImg = pygame.image.load('{}/img/newSceneClicked.png'.format(SCRIPT_PATH))
    highlightedImg = pygame.image.load('{}/img/newSceneHighlighted.png'.format(SCRIPT_PATH))
    super(NewSceneButton, self).__init__(name,
                                         buttonRect,
                                         img,
                                         clickedImg,
                                         highlightedImg)

  def clickAction(self, override=False):
    # Check if the button is enabled
    if not override:
      try:
        super(NewSceneButton, self).clickAction()
      except:
        return None
    if areYouSure('Create new Scene?\n\nUnsaved changes will be lost!'):
      purgeScene()
      setWindowTitle('New Scene')
      infoMessage('New Scene!')
      undoHistory.clear()
      getObjectByName('undoButton').disable()
      redoHistory.clear()
      getObjectByName('redoButton').disable()

  def tooltip(self, screen, mousePos=None):
    super(NewSceneButton, self).tooltip(screen, mousePos, "NewSceneButton")



class LoadSceneButton(Button):
  def __init__(self, name="LoadSceneButton",
               buttonRect=pygame.Rect(0,0,0,0),
               buttonSurfaceObj=pygame.Surface((0,0)),
               buttonClickedSurfaceObj=pygame.Surface((0,0))):
    img = pygame.image.load('{}/img/loadScene.png'.format(SCRIPT_PATH))
    clickedImg = pygame.image.load('{}/img/loadSceneClicked.png'.format(SCRIPT_PATH))
    highlightedImg = pygame.image.load('{}/img/loadSceneHighlighted.png'.format(SCRIPT_PATH))
    super(LoadSceneButton, self).__init__(name,
                                          buttonRect,
                                          img,
                                          clickedImg,
                                          highlightedImg)
    self.lastFile = ''
    self.lastDir  = ''

  def clickAction(self, override=False):
    # Check if the button is enabled
    if not override:
      try:
        super(LoadSceneButton, self).clickAction()
      except:
        return None
    # GTK
    chooser = gtk.FileChooserDialog(title='Mayday Level Editor - Load scene',
                                    action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                    buttons=(gtk.STOCK_CANCEL,
                                             gtk.RESPONSE_CANCEL,
                                             gtk.STOCK_OPEN,
                                             gtk.RESPONSE_OK))
    chooser.set_current_folder(SCRIPT_PATH)
    ffilter = gtk.FileFilter()
    ffilter.set_name("Python shelved data")
    ffilter.add_pattern("*.shelve")
    chooser.add_filter(ffilter)
    if self.lastDir:
      chooser.set_current_folder(self.lastDir)
    response = chooser.run()
    if response == gtk.RESPONSE_OK:
      filename = chooser.get_filename()
      if areYouSure('Load scene %s?\n\nUnsaved changes to the current scene will be lost!' % filename):
        # Delete current scene
        purgeScene()
        self.lastDir, self.lastFile = os.path.split(filename)
        db = shelve.open(filename)
        sceneData = db['objectslist']
        # Reconstruct scene
        deserializeScene(sceneData)
        db.close()
        # Clear the undo and redo history
        undoHistory.clear()
        getObjectByName('undoButton').disable()
        redoHistory.clear()
        getObjectByName('redoButton').disable()
        setWindowTitle(filename, False)
        infoMessage('%s loaded' % filename)
    chooser.destroy()
    # Force GTK to empty its event loop, else a dialog window gets stuck
    while gtk.events_pending():
      gtk.main_iteration()

  def tooltip(self, screen, mousePos=None):
    super(LoadSceneButton, self).tooltip(screen, mousePos, "LoadSceneButton")



class SaveSceneButton(Button):
  def __init__(self, name="SaveSceneButton",
               buttonRect=pygame.Rect(0,0,0,0),
               buttonSurfaceObj=pygame.Surface((0,0)),
               buttonClickedSurfaceObj=pygame.Surface((0,0))):
    img = pygame.image.load('{}/img/saveScene.png'.format(SCRIPT_PATH))
    clickedImg = pygame.image.load('{}/img/saveSceneClicked.png'.format(SCRIPT_PATH))
    highlightedImg = pygame.image.load('{}/img/saveSceneHighlighted.png'.format(SCRIPT_PATH))
    super(SaveSceneButton, self).__init__(name,
                                          buttonRect,
                                          img,
                                          clickedImg,
                                          highlightedImg)
    self.lastFile = ''
    self.lastDir  = ''

  def clickAction(self, override=False):
    # Check if the button is enabled
    if not override:
      try:
        super(SaveSceneButton, self).clickAction()
      except:
        return None
    # GTK
    chooser = gtk.FileChooserDialog(title='Mayday Level Editor - Save scene',
                                    action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                    buttons=(gtk.STOCK_CANCEL,
                                             gtk.RESPONSE_CANCEL,
                                             gtk.STOCK_SAVE,
                                             gtk.RESPONSE_OK))
    chooser.set_current_folder(SCRIPT_PATH)
    ffilter = gtk.FileFilter()
    ffilter.set_name("Python shelved data")
    ffilter.add_pattern("*.shelve")
    chooser.add_filter(ffilter)
    if self.lastDir:
      chooser.set_current_folder(self.lastDir)
    if self.lastFile:
      chooser.set_current_name(self.lastFile)
    else:
      chooser.set_current_name('NewScene.shelve')
    response = chooser.run()
    if response == gtk.RESPONSE_OK:
      filename = chooser.get_filename()
      if not os.path.isfile(filename) or \
         areYouSure('Overwrite file %s?' % filename):
        self.lastDir, self.lastFile = os.path.split(filename)
        # TODO confirm overwrite?
        db = shelve.open(filename)
        db['objectslist'] = serializeScene()
        db.close()
        setWindowTitle(filename, False)
        infoMessage('%s saved' % filename)
    chooser.destroy()
    # Force GTK to empty its event loop, else a dialog window gets stuck
    while gtk.events_pending():
      gtk.main_iteration()

  def tooltip(self, screen, mousePos=None):
    super(SaveSceneButton, self).tooltip(screen, mousePos, "SaveSceneButton")



class ExitProgramButton(Button):
  def __init__(self, name="ExitProgramButton",
               buttonRect=pygame.Rect(0,0,0,0),
               buttonSurfaceObj=pygame.Surface((0,0)),
               buttonClickedSurfaceObj=pygame.Surface((0,0))):
    img = pygame.image.load('{}/img/exitProgram.png'.format(SCRIPT_PATH))
    clickedImg = pygame.image.load('{}/img/exitProgramClicked.png'.format(SCRIPT_PATH))
    highlightedImg = pygame.image.load('{}/img/exitProgramHighlighted.png'.format(SCRIPT_PATH))
    super(ExitProgramButton, self).__init__(name,
                                            buttonRect,
                                            img,
                                            clickedImg,
                                            highlightedImg)

  def clickAction(self, override=False):
    # Check if the button is enabled
    if not override:
      try:
        super(ExitProgramButton, self).clickAction()
      except:
        return None
    # Ask for user confirmation
    if areYouSure('Quit Mayday Level Editor?'):
      pygame.event.post(pygame.event.Event(pygame.QUIT))

  def tooltip(self, screen, mousePos=None):
    super(ExitProgramButton, self).tooltip(screen, mousePos, "ExitProgramButton")



class UndoButton(Button):
  def __init__(self, name="UndoButton",
               buttonRect=pygame.Rect(0,0,0,0),
               buttonSurfaceObj=pygame.Surface((0,0)),
               buttonClickedSurfaceObj=pygame.Surface((0,0))):
    img = pygame.image.load('{}/img/undo.png'.format(SCRIPT_PATH))
    clickedImg = pygame.image.load('{}/img/undoClicked.png'.format(SCRIPT_PATH))
    highlightedImg = pygame.image.load('{}/img/undoHighlighted.png'.format(SCRIPT_PATH))
    super(UndoButton, self).__init__(name,
                                            buttonRect,
                                            img,
                                            clickedImg,
                                            highlightedImg)

  def clickAction(self):
    # Check if the button is enabled
    try:
      super(UndoButton, self).clickAction()
    except:
      return None
    undo()

  def tooltip(self, screen, mousePos=None):
    super(UndoButton, self).tooltip(screen, mousePos, "UndoButton")



class RedoButton(Button):
  def __init__(self, name="RedoButton",
               buttonRect=pygame.Rect(0,0,0,0),
               buttonSurfaceObj=pygame.Surface((0,0)),
               buttonClickedSurfaceObj=pygame.Surface((0,0))):
    img = pygame.image.load('{}/img/redo.png'.format(SCRIPT_PATH))
    clickedImg = pygame.image.load('{}/img/redoClicked.png'.format(SCRIPT_PATH))
    highlightedImg = pygame.image.load('{}/img/redoHighlighted.png'.format(SCRIPT_PATH))
    super(RedoButton, self).__init__(name,
                                            buttonRect,
                                            img,
                                            clickedImg,
                                            highlightedImg)

  def clickAction(self):
    # Check if the button is enabled
    try:
      super(RedoButton, self).clickAction()
    except:
      return None
    redo()

  def tooltip(self, screen, mousePos=None):
    super(RedoButton, self).tooltip(screen, mousePos, "RedoButton")



class PathPiece(ClickRegisteringObject):
  def __init__(self):
    self.activeEndPixelPos = (0,0)
    self.inactiveEndPixelPos = (0,0)
    super(PathPiece, self).__init__()

  def shelve(self):
    pass

  def cursorOnEnd(self, mousePos=None, activeEnd=True):
    if mousePos is None:
      mousePos = pygame.mouse.get_pos()
    if not self.rect.collidepoint(mousePos):
      return False
    ppos = self.activeEndPixelPos if activeEnd else self.inactiveEndPixelPos
    return (mousePos[0]-CLICK_TOLERANCE_RADIUS-ppos[0])**2 + \
           (mousePos[1]-CLICK_TOLERANCE_RADIUS-ppos[1])**2   < CLICK_TOLERANCE_RADIUS**2-1

  #def noTuplesPlease(self):
  #  """BUGFIX FUNCTION: Asserts that self.center is NOT a tuple"""
  #  if isinstance(self.center, tuple):
  #    logging.debug("CAUTION: %s.noTuplesPlease() fired!" % self.__class__.__name__)
  #    self.center = [i for i in self.center]



class Straight(PathPiece):
  def __init__(self,
               startPoint3D=Point3D(),
               endPoint3D=Point3D(),
               color=(0,0,255)):
    super(Straight, self).__init__()
    self.startPoint = Point3D.copy(startPoint3D)
    self.endPoint = Point3D.copy(endPoint3D)
    self.color = color
    #[(a+b)/2. for a,b in zip(startPoint3D, endPoint3D)]
    self.center = (startPoint3D+endPoint3D)/2
    self.activeEnd = 0
    self.render()

  def shelve(self):
    """Save a Straight instance to file"""
    d = [self.startPoint,
         self.endPoint,
         self.color[:],
         self.center,
         self.activeEnd]
    return d

  def unshelve(self, shelvedData):
    """Load a Straight instance from file"""
    self.startPoint,    \
    self.endPoint,      \
    self.color,         \
    self.center,        \
    self.activeEnd = shelvedData

  def moveTo(self, newPos):
    #[(i-j) for i,j in zip(self.startPoint, self.center)]
    startOffset = self.startPoint - self.center
    #[(i-j) for i,j in zip(self.endPoint, self.center)]
    endOffset = self.endPoint - self.center
    super(Straight, self).moveTo(newPos)
    #tuple([(i+j) for i,j in zip(startOffset, self.center)])
    self.startPoint = startOffset + self.center
    #tuple([(i+j) for i,j in zip(endOffset, self.center)])
    self.endPoint = endOffset + self.center
    self.render()

  def render(self, highdefinition=False):
    """Call after viewing direction or zoom change to rerender object"""

    #gradient = [i-j for i,j in zip(self.startPoint, self.endPoint)]
    #print "gradient: ", gradient

    positions = (project3dToPixelPosition(self.startPoint, ORIGIN),
                 project3dToPixelPosition(self.endPoint, ORIGIN))
    colors = (self.color)
    min_x = int(min([p[0] for p in positions]))
    max_x = int(max([p[0] for p in positions]))
    min_y = int(min([p[1] for p in positions]))
    max_y = int(max([p[1] for p in positions]))
    start = positions[0]
    end = positions[1]
    # Safely overestimate the needed area (pad to avoid clipping lines)
    tempSurfaceObj = pygame.Surface((max_x-min_x+3*CLICK_TOLERANCE_RADIUS,
                                     max_y-min_y+3*CLICK_TOLERANCE_RADIUS))
    tempSurfaceObj = tempSurfaceObj.convert_alpha()
    tempSurfaceObjCenter = [tempSurfaceObj.get_size()[0]//2,
                            tempSurfaceObj.get_size()[1]//2]

    linecenter = project3dToPixelPosition((self.endPoint+self.startPoint)/2,
                                          ORIGIN)
    pygame.draw.aaline(tempSurfaceObj, self.color,
                       (positions[0][0]-linecenter[0]+tempSurfaceObjCenter[0],
                        positions[0][1]-linecenter[1]+tempSurfaceObjCenter[1]),
                       (positions[1][0]-linecenter[0]+tempSurfaceObjCenter[0],
                        positions[1][1]-linecenter[1]+tempSurfaceObjCenter[1]))

    # Repair the alpha values (transparency) at antialiasing border
    pixels = pygame.PixelArray(tempSurfaceObj)
    pixels.replace(pygame.Color(0, 0, 0, 255), pygame.Color(0, 0, 0, 0))
    del pixels
    tempSurfaceObjRect = tempSurfaceObj.get_rect()
    tempSurfaceObjRect.center = linecenter
    self.surfaceObj = tempSurfaceObj
    self.rect = tempSurfaceObjRect

    # Mark the active end
    pos  = self.startPoint if self.activeEnd == 0 else self.endPoint
    ppos = project3dToPixelPosition(pos)
    self.activeEndPixelPos = (int(ppos[0])-CLICK_TOLERANCE_RADIUS,
                              int(ppos[1])-CLICK_TOLERANCE_RADIUS)
    pos  = self.endPoint if self.activeEnd == 0 else self.startPoint
    ppos = project3dToPixelPosition(pos)
    self.inactiveEndPixelPos = (int(ppos[0])-CLICK_TOLERANCE_RADIUS,
                                int(ppos[1])-CLICK_TOLERANCE_RADIUS)

  def getEndPoint3d(self, getActiveEnd):
    return self.startPoint if (self.activeEnd==0 and getActiveEnd) or  \
                              (self.activeEnd==1 and not getActiveEnd) \
                           else self.endPoint

  def setEndPos3d(self, newPos, setActiveEnd):
    #self.noTuplesPlease()
    if (self.activeEnd==0 and setActiveEnd) or  \
       (self.activeEnd==1 and not setActiveEnd):
      self.startPoint = Point3D.copy(newPos)
    else:
      self.endPoint = Point3D.copy(newPos)
    self.center = (self.startPoint + self.endPoint)/2
    self.render()

  def draw(self, screen):
    # Mark the active end
    if self.selected:
      screen.blit(markring, self.activeEndPixelPos)
      screen.blit(markdot, self.activeEndPixelPos)
      screen.blit(markring, self.inactiveEndPixelPos)
    super(Straight, self).draw(screen)


class HelixArc(PathPiece):
  # Number of frames to wait until rendering in high resolution
  _HQFrameDelay = 3

  def __init__(self,
               startHeight=-40., endHeight=40.,
               startAngle=0., endAngle=360.,
               radius=50., center=Point3D(),
               rightHanded=True, color=(0,0,255),
               gamma=1.):
    super(HelixArc, self).__init__()
    self.center = Point3D.copy(center)
    self.centershift = [0,0]
    self.color = color
    self.startAngle, self.endAngle = startAngle, endAngle
    self.startHeight, self.endHeight = startHeight, endHeight
    self.rightHanded = rightHanded
    self.radius = radius
    self.activeEndPixelPos = [0,0]
    self.inactiveEndPixelPos = [0,0]
    ## The gamma value controls the gradient of the HelixArc's steepness
    #  It's called "gamma" because it follows a gamma correction-style curve
    self.gamma = gamma
    self.activeEnd = 0
    self.bezierControls = []
    self.recompute()
    self.render()

  def shelve(self):
    """Save a HelixArc instance to file"""
    d = [self.center,
         self.centershift[:],
         self.color[:],
         self.startAngle,
         self.endAngle,
         self.startHeight,
         self.endHeight,
         self.rightHanded,
         self.radius,
         self.activeEnd,
         self.gamma]
    return d

  def unshelve(self, shelvedData):
    """Load a HelixArc instance from file"""
    self.center,                  \
    self.centershift,             \
    self.color,                   \
    self.startAngle,              \
    self.endAngle,                \
    self.startHeight,             \
    self.endHeight,               \
    self.rightHanded,             \
    self.radius,                  \
    self.activeEnd,               \
    self.gamma = shelvedData
    self.recompute()

  def recompute(self):
    height, angle = self.startHeight, self.startAngle
    self.points3d = []
    self.points3dHD = []
    step = 0
    steps = int((self.endAngle - self.startAngle) * abs(self.radius)/50)
    # Avoid nasty divide-by-zero errors
    steps = max(100, steps)
    # Limit the number of samples to avoid lag
    steps = min(2500, steps)
    heightstep = (self.endHeight-self.startHeight)/steps
    anglestep = (self.endAngle-self.startAngle)/steps
    """# Sample points along the curve
    for step in range(steps):
      a = angle if self.rightHanded else (360.-angle)
      x = cos(a*(pi/180.))*self.radius
      y = sin(a*(pi/180.))*self.radius
      # Gamma correction-style height recomputation (keeps range)
      z = self.startHeight + \
            (self.endHeight-self.startHeight) * \
            ((height-self.startHeight)/(self.endHeight-self.startHeight)) ** \
              (1./self.gamma)
      # Enable drawing in low and high resolution
      self.points3dHD.append(Point3D(x,y,z))
      # Ensure that the first and last point are in the low res samples
      if step % 10 == 0 or step == steps-1:
        self.points3d.append(Point3D(x,y,z))
      angle += anglestep
      height += heightstep"""

    # Bezier curve computation
    self.points3d = self.points3dHD = []
    # Control points
    P0 = Point3D(self.startAngle, self.startHeight,    0.)
    P1 = Point3D(self.startAngle, self.startHeight+200, 0.)
    P2 = Point3D(self.endAngle,   self.endHeight-200,   0.)
    P3 = Point3D(self.endAngle,   self.endHeight,      0.)
    for step in range(steps+1):
      t = step/float(steps)
      # Cubic Bezier curve, explicit formula (en.wikipedia.org: Bezier curve)
      B =     (1-t)**3        * P0 + \
          3 * (1-t)**2 * t    * P1 + \
          3 * (1-t)    * t**2 * P2 + \
                         t**3 * P3
      a = B.x if self.rightHanded else (360.-B.x)
      x = cos(a*(pi/180.))*self.radius
      y = sin(a*(pi/180.))*self.radius
      z = B.y
      # Enable drawing in low and high resolution
      self.points3dHD.append(Point3D(x,y,z))
      # Ensure that the first and last point are in the low res samples
      if step % 10 == 0 or step == steps-1:
        self.points3d.append(Point3D(x,y,z))
      angle += anglestep
      height += heightstep


  def getEndPoint3d(self, getActiveEnd):
    return self.points3d[0] if (self.activeEnd==0 and getActiveEnd) or  \
                               (self.activeEnd==1 and not getActiveEnd) \
                            else self.points3d[-1]

  def setEndPos3d(self, newPos, setActiveEnd):
    #self.noTuplesPlease()
    endIndexInPoints3d = 0 if (self.activeEnd==0 and setActiveEnd) or  \
                              (self.activeEnd==1 and not setActiveEnd) \
                           else -1
    hDelta = newPos.z - self.points3d[endIndexInPoints3d].z
    if (self.activeEnd==0 and setActiveEnd) or  \
       (self.activeEnd==1 and not setActiveEnd):
      self.startHeight += .25*hDelta
      self.endHeight   -= .5*hDelta
      self.center.z    += .5*hDelta
    else:
      self.startHeight -= .5*hDelta
      self.endHeight   += .25*hDelta
      self.center.z    += .5*hDelta
    self.recompute()
    self.render(True)

  def changeAngles(self, mouseRel, setActiveEnd):
    if (self.activeEnd==0 and setActiveEnd) or  \
       (self.activeEnd==1 and not setActiveEnd):
      self.startAngle -= mouseRel[0]
    else:
      self.endAngle += mouseRel[0]
    self.recompute()
    self.render(True)

  def moveTo(self, newPos):
    super(HelixArc, self).moveTo(newPos)
    self.render(True)

  def render(self, highdefinition=False):
    """
    If highdefinition is FALSE, the HelixArc will be rendered using 100 sample
    points. If highdefinition is TRUE, 1000 points will be used instead.
    """
    minx, miny, maxx, maxy = 9999.,9999.,-9999.,-9999.
    points = self.points3dHD if highdefinition else self.points3d
    pixels = []
    for p in points:
      px, py = project3dToPixelPosition(p, (0,0))
      pixels.append(((px,py), p.z+self.center.z))
      minx=min(minx,px)
      miny=min(miny,py)
      maxx=max(maxx,px)
      maxy=max(maxy,py)
    # Padding the image avoids clipping pixels
    pad = CLICK_TOLERANCE_RADIUS
    self.centershift = [(maxx+minx)/2,(maxy+miny)/2]
    sf = pygame.Surface((maxx-minx+2*pad,maxy-miny+2*pad))
    sf = sf.convert_alpha()
    sf.fill((0,0,0,0))
    sfsize=sf.get_size()
    self.surfaceObj = sf

    # Mark the active end
    pos  = self.points3d[0] if self.activeEnd == 0 else self.points3d[-1]
    ppos = project3dToPixelPosition(pos)
    self.activeEndPixelPos = (int(ppos[0])-CLICK_TOLERANCE_RADIUS,
                              int(ppos[1])-CLICK_TOLERANCE_RADIUS)
    pos  = self.points3d[-1] if self.activeEnd == 0 else self.points3d[0]
    ppos = project3dToPixelPosition(pos)
    self.inactiveEndPixelPos = (int(ppos[0])-CLICK_TOLERANCE_RADIUS,
                                int(ppos[1])-CLICK_TOLERANCE_RADIUS)

    # Draw sample points, using Wu-style antialiasing
    # NOTE that AA is performed using only the alpha channel!
    for p, z in pixels:
      # Color pixels that are "below" the (z=0)-plane differently
      drawcolor = self.color if z >= 0 \
                             else (127,127,255)
      xint, xfrac = divmod(p[0], 1)
      yint, yfrac = divmod(p[1], 1)

      if 0 <= int(xint)-int(minx)+pad < WINDOW_SIZE[0] and \
         0 <= int(yint)-int(miny)+pad < WINDOW_SIZE[1]:
        c = sf.get_at((int(xint)-int(minx)+pad,int(yint)-int(miny)+pad))
        c.r, c.g, c.b = drawcolor
        c.a=max(c.a,int(255*(1.-xfrac)*(1.-yfrac)))
        sf.set_at((int(xint)-int(minx)+pad,int(yint)-int(miny)+pad),c)

      if 0 <= int(xint)+1-int(minx)+pad < WINDOW_SIZE[0] and \
         0 <= int(yint)-int(miny)+pad < WINDOW_SIZE[1]:
        c = sf.get_at((int(xint)+1-int(minx)+pad,int(yint)-int(miny)+pad))
        c.r, c.g, c.b = drawcolor
        c.a=max(c.a,int(255*(xfrac)*(1.-yfrac)))
        sf.set_at((int(xint)+1-int(minx)+pad,int(yint)-int(miny)+pad),c)

      if 0 <= int(xint)-int(minx)+pad < WINDOW_SIZE[0] and \
         0 <= int(yint)+1-int(miny)+pad < WINDOW_SIZE[1]:
        c = sf.get_at((int(xint)-int(minx)+pad,int(yint)+1-int(miny)+pad))
        c.r, c.g, c.b = drawcolor
        c.a=max(c.a,int(255*(1.-xfrac)*(yfrac)))
        sf.set_at((int(xint)-int(minx)+pad,int(yint)+1-int(miny)+pad),c)

      if 0 <= int(xint)+1-int(minx)+pad < WINDOW_SIZE[0] and \
         0 <= int(yint)+1-int(miny)+pad < WINDOW_SIZE[1]:
        c = sf.get_at((int(xint)+1-int(minx)+pad,int(yint)+1-int(miny)+pad))
        c.r, c.g, c.b = drawcolor
        c.a=max(c.a,int(255*(xfrac)*(yfrac)))
        sf.set_at((int(xint)+1-int(minx)+pad,int(yint)+1-int(miny)+pad),c)

    r = sf.get_rect()
    r.center = [ORIGIN[0]+self.centershift[0], ORIGIN[1]+self.centershift[1]]
    self.rect = r

  def draw(self, screen):
    """
    The HelixArc needs special treatment, as its boundingbox depends heavily
    on the viewing direction.
    """
    if self.selected:
      pos  = self.points3d[0] if self.activeEnd == 0 else self.points3d[-1]
      ppos = project3dToPixelPosition(pos + self.center)
      self.activeEndPixelPos = (int(ppos[0])-CLICK_TOLERANCE_RADIUS,
                                int(ppos[1])-CLICK_TOLERANCE_RADIUS)
      pos  = self.points3d[-1] if self.activeEnd == 0 else self.points3d[0]
      ppos = project3dToPixelPosition(pos + self.center)
      self.inactiveEndPixelPos = (int(ppos[0])-CLICK_TOLERANCE_RADIUS,
                                  int(ppos[1])-CLICK_TOLERANCE_RADIUS)
      screen.blit(markring, self.activeEndPixelPos)
      screen.blit(markdot, self.activeEndPixelPos)
      screen.blit(markring, self.inactiveEndPixelPos)
    ppos = project3dToPixelPosition(self.center)
    self.rect.center = [ppos[0]+self.centershift[0],
                        ppos[1]+self.centershift[1]]
    screen.blit(self.surfaceObj, self.rect)


class BezierArc(PathPiece):
  # Number of frames to wait until rendering in high resolution
  _HQFrameDelay = 3

  def __init__(self,
               startPoint3D=Point3D(),
               endPoint3D=Point3D(),
               bezierControlStartPoint3D=Point3D(),
               bezierControlEndPoint3D=Point3D(),
               color=(0,0,255)):
    """Bezier Points are OFFSETS to the respective point!"""
    super(BezierArc, self).__init__()
    self.centershift = [0,0]
    self.color = color
    self.startPoint = Point3D.copy(startPoint3D)
    self.endPoint = Point3D.copy(endPoint3D)
    self.activeEndPixelPos = [0,0]
    self.inactiveEndPixelPos = [0,0]
    self.bezierControlStartPixelPos = [0,0]
    self.bezierControlEndPixelPos = [0,0]
    self.activeEnd = 0
    self.bezierControlStartPoint = Point3D.copy(bezierControlStartPoint3D)
    self.bezierControlEndPoint = Point3D.copy(bezierControlEndPoint3D)
    self.center = (self.startPoint+self.endPoint)/2
    self.recompute()
    self.render()

  def shelve(self):
    """Save a BezierArc instance to file"""
    d = [self.center,
         self.color[:],
         self.startPoint,
         self.endPoint,
         self.bezierControlStartPoint,
         self.bezierControlEndPoint,
         self.activeEnd]
    return d

  def unshelve(self, shelvedData):
    """Load a BezierArc instance from file"""
    self.center,                  \
    self.color,                   \
    self.startPoint,              \
    self.endPoint,                \
    self.bezierControlStartPoint, \
    self.bezierControlEndPoint,   \
    self.activeEnd = shelvedData
    self.recompute()

  def recompute(self):
    self.points3d = []
    self.points3dHD = []
    step = 0
    steps = 100
    # Avoid nasty divide-by-zero errors
    steps = max(100, steps)
    # Limit the number of samples to avoid lag
    steps = min(2500, steps)
    # Bezier curve computation
    self.points3d = self.points3dHD = []
    # Control points
    P0 = self.startPoint
    P1 = self.startPoint + self.bezierControlStartPoint
    P2 = self.endPoint + self.bezierControlEndPoint
    P3 = self.endPoint
    for step in range(steps+1):
      t = step/float(steps)
      # Cubic Bezier curve, explicit formula (en.wikipedia.org: Bezier curve)
      B =     (1-t)**3        * P0 + \
          3 * (1-t)**2 * t    * P1 + \
          3 * (1-t)    * t**2 * P2 + \
                         t**3 * P3
      # Enable drawing in low and high resolution
      self.points3dHD.append(B)
      # Ensure that the first and last point are in the low res samples
      if step % 10 == 0 or step == steps-1:
        self.points3d.append(B)

  def cursorOnBezierControl(self, mousePos=None, _start=True):
    if mousePos is None:
      mousePos = pygame.mouse.get_pos()
    if not self.rect.collidepoint(mousePos):
      return False
    ppos = self.bezierControlStartPixelPos  \
            if _start                       \
            else self.bezierControlEndPixelPos
    print mousePos, ppos
    return ((mousePos[0]-CLICK_TOLERANCE_RADIUS-ppos[0])**2 + \
            (mousePos[1]-CLICK_TOLERANCE_RADIUS-ppos[1])**2)  \
           < CLICK_TOLERANCE_RADIUS**2-1

  def getEndPoint3d(self, getActiveEnd):
    return self.points3d[0] if (self.activeEnd==0 and getActiveEnd) or  \
                               (self.activeEnd==1 and not getActiveEnd) \
                            else self.points3d[-1]

  def setEndPos3d(self, newPos, setActiveEnd):
    endIndexInPoints3d = 0 if (self.activeEnd==0 and setActiveEnd) or  \
                              (self.activeEnd==1 and not setActiveEnd) \
                           else -1
    delta = newPos - self.points3d[endIndexInPoints3d]
    if (self.activeEnd==0 and setActiveEnd) or  \
       (self.activeEnd==1 and not setActiveEnd):
      self.startPoint += .25 * delta
      self.endPoint   -= .5  * delta
      self.center     += .5  * delta
    else:
      self.startPoint -= .5  * delta
      self.endPoint   += .25 * delta
      self.center     += .5  * delta
    self.recompute()
    self.render(True)

  def getBezierControl(self, getStart):
    return self.bezierControlStartPoint \
            if getStart                 \
            else self.bezierControlEndPoint

  def setBezierControl(self, newPos, setStart):
    if setStart:
      self.bezierControlStartPoint = Point3D.copy(newPos)
    else:
      self.bezierControlEndPoint   = Point3D.copy(newPos)
    handle = Point3D.copy(newPos)
    self.recompute()
    self.render(True)

  def moveTo(self, newPos):
    super(BezierArc, self).moveTo(newPos)
    self.render(True)

  def render(self, highdefinition=False):
    """
    If highdefinition is FALSE, the HelixArc will be rendered using 100 sample
    points. If highdefinition is TRUE, 1000 points will be used instead.
    """
    minx, miny, maxx, maxy = 9999.,9999.,-9999.,-9999.
    points = self.points3dHD if highdefinition else self.points3d
    pixels = []
    for p in points+[self.startPoint+self.bezierControlStartPoint,
                     self.endPoint+self.bezierControlEndPoint]:
      px, py = project3dToPixelPosition(p, (0,0))
      pixels.append(((px,py), p.z+self.center.z))
      minx=min(minx,px)
      miny=min(miny,py)
      maxx=max(maxx,px)
      maxy=max(maxy,py)
    # The Bezier control points should not be drawn as points, so take them out
    pixels[-2:] = []
    # Padding the image avoids clipping pixels
    pad = CLICK_TOLERANCE_RADIUS
    self.centershift = [(maxx+minx)/2,(maxy+miny)/2]
    sf = pygame.Surface((maxx-minx+2*pad,maxy-miny+2*pad))
    sf = sf.convert_alpha()
    sf.fill((0,0,0,0))
    sfsize=sf.get_size()
    self.surfaceObj = sf

    pos  = self.points3d[0] if self.activeEnd == 0 else self.points3d[-1]
    ppos = project3dToPixelPosition(pos + self.center)
    self.activeEndPixelPos = (int(ppos[0])-CLICK_TOLERANCE_RADIUS,
                              int(ppos[1])-CLICK_TOLERANCE_RADIUS)
    pos  = self.points3d[-1] if self.activeEnd == 0 else self.points3d[0]
    ppos = project3dToPixelPosition(pos + self.center)
    self.inactiveEndPixelPos = (int(ppos[0])-CLICK_TOLERANCE_RADIUS,
                                int(ppos[1])-CLICK_TOLERANCE_RADIUS)
    pos  = self.startPoint+self.bezierControlStartPoint
    ppos = project3dToPixelPosition(pos + self.center)
    self.bezierControlStartPixelPos = (int(ppos[0])-CLICK_TOLERANCE_RADIUS,
                                       int(ppos[1])-CLICK_TOLERANCE_RADIUS)
    pos  = self.endPoint+self.bezierControlEndPoint
    ppos = project3dToPixelPosition(pos + self.center)
    self.bezierControlEndPixelPos = (int(ppos[0])-CLICK_TOLERANCE_RADIUS,
                                     int(ppos[1])-CLICK_TOLERANCE_RADIUS)

    # Draw sample points, using Wu-style antialiasing
    # NOTE that AA is performed using only the alpha channel!
    for p, z in pixels:
      # Color pixels that are "below" the (z=0)-plane differently
      drawcolor = self.color if z >= 0 \
                             else (127,127,255)
      xint, xfrac = divmod(p[0], 1)
      yint, yfrac = divmod(p[1], 1)

      if 0 <= int(xint)-int(minx)+pad < WINDOW_SIZE[0] and \
         0 <= int(yint)-int(miny)+pad < WINDOW_SIZE[1]:
        c = sf.get_at((int(xint)-int(minx)+pad,int(yint)-int(miny)+pad))
        c.r, c.g, c.b = drawcolor
        c.a=max(c.a,int(255*(1.-xfrac)*(1.-yfrac)))
        sf.set_at((int(xint)-int(minx)+pad,int(yint)-int(miny)+pad),c)

      if 0 <= int(xint)+1-int(minx)+pad < WINDOW_SIZE[0] and \
         0 <= int(yint)-int(miny)+pad < WINDOW_SIZE[1]:
        c = sf.get_at((int(xint)+1-int(minx)+pad,int(yint)-int(miny)+pad))
        c.r, c.g, c.b = drawcolor
        c.a=max(c.a,int(255*(xfrac)*(1.-yfrac)))
        sf.set_at((int(xint)+1-int(minx)+pad,int(yint)-int(miny)+pad),c)

      if 0 <= int(xint)-int(minx)+pad < WINDOW_SIZE[0] and \
         0 <= int(yint)+1-int(miny)+pad < WINDOW_SIZE[1]:
        c = sf.get_at((int(xint)-int(minx)+pad,int(yint)+1-int(miny)+pad))
        c.r, c.g, c.b = drawcolor
        c.a=max(c.a,int(255*(1.-xfrac)*(yfrac)))
        sf.set_at((int(xint)-int(minx)+pad,int(yint)+1-int(miny)+pad),c)

      if 0 <= int(xint)+1-int(minx)+pad < WINDOW_SIZE[0] and \
         0 <= int(yint)+1-int(miny)+pad < WINDOW_SIZE[1]:
        c = sf.get_at((int(xint)+1-int(minx)+pad,int(yint)+1-int(miny)+pad))
        c.r, c.g, c.b = drawcolor
        c.a=max(c.a,int(255*(xfrac)*(yfrac)))
        sf.set_at((int(xint)+1-int(minx)+pad,int(yint)+1-int(miny)+pad),c)

    r = sf.get_rect()
    r.center = [ORIGIN[0]+self.centershift[0], ORIGIN[1]+self.centershift[1]]
    self.rect = r

  def draw(self, screen):
    """
    The BezierArc needs special treatment, as its boundingbox depends heavily
    on the viewing direction.
    """
    if self.selected:
      """pos  = self.points3d[0] if self.activeEnd == 0 else self.points3d[-1]
      ppos = project3dToPixelPosition(pos + self.center)
      self.activeEndPixelPos = (int(ppos[0])-CLICK_TOLERANCE_RADIUS,
                                int(ppos[1])-CLICK_TOLERANCE_RADIUS)
      pos  = self.points3d[-1] if self.activeEnd == 0 else self.points3d[0]
      ppos = project3dToPixelPosition(pos + self.center)
      self.inactiveEndPixelPos = (int(ppos[0])-CLICK_TOLERANCE_RADIUS,
                                  int(ppos[1])-CLICK_TOLERANCE_RADIUS)
      pos  = self.startPoint+self.bezierControlStartPoint
      ppos = project3dToPixelPosition(pos + self.center)
      self.bezierControlStartPixelPos = (int(ppos[0])-CLICK_TOLERANCE_RADIUS,
                                         int(ppos[1])-CLICK_TOLERANCE_RADIUS)
      pos  = self.endPoint+self.bezierControlEndPoint
      ppos = project3dToPixelPosition(pos + self.center)
      self.bezierControlEndPixelPos = (int(ppos[0])-CLICK_TOLERANCE_RADIUS,
                                       int(ppos[1])-CLICK_TOLERANCE_RADIUS)"""

      drawPotentialConnectionLine(self.startPoint+self.center,
                                  self.startPoint+self.center+self.bezierControlStartPoint,
                                  screen)
      drawPotentialConnectionLine(self.endPoint+self.center,
                                  self.endPoint+self.center+self.bezierControlEndPoint,
                                  screen)

      screen.blit(markring,       self.activeEndPixelPos)
      screen.blit(markdot,        self.activeEndPixelPos)
      screen.blit(markring,       self.inactiveEndPixelPos)
      screen.blit(markrectangle,  self.bezierControlStartPixelPos)
      screen.blit(markrectangle,  self.bezierControlEndPixelPos)
    ppos = project3dToPixelPosition(self.center)
    self.rect.center = [ppos[0]+self.centershift[0],
                        ppos[1]+self.centershift[1]]
    screen.blit(self.surfaceObj, self.rect)


#_______________________________________________________________________


def areYouSure(text=None):
  """GTK function to ask for user confirmation"""
  pdialog = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                              buttons=gtk.BUTTONS_YES_NO)
  if text is not None:
    pdialog.set_markup(text)
  #pdialog.format_secondary_text("title")
  response = pdialog.run()
  result = True if response==gtk.RESPONSE_YES else False
  pdialog.destroy()
  # Force GTK to empty its event loop, else a dialog window gets stuck
  while gtk.events_pending():
    gtk.main_iteration()
  return result

def purgeScene():
  """Completely kill the current scene"""
  global objectsList
  deselectObjects()
  objectsList = [o for o in objectsList if isinstance(o, Button)]

def serializeScene():
  """Save all PathPiece instances"""
  return [(o.__class__.__name__, o.shelve()) for o in objectsList
                                             if not isinstance(o, Button)]

def deserializeScene(data):
  """Reconstruct PathPiece instances from serialized data"""
  global objectsList
  classes = {'Straight': Straight,
             'HelixArc': HelixArc,
             'BezierArc': BezierArc}
  for classname, shelvedObj in data:
    o = classes[classname]()
    o.unshelve(shelvedObj)
    objectsList.append(o)
    o.render(True)

def createUndoHistory(newstep=True):
  """Saves the current scene state into the undo history"""
  state = serializeScene()
  undoHistory.append(state)
  # Adding a new undo step clears the redo history
  getObjectByName('undoButton').enable()
  if newstep:
    redoHistory.clear()
    getObjectByName('redoButton').disable()

def createRedoHistory():
  """Saves the current scene state into the undo history"""
  state = serializeScene()
  redoHistory.appendleft(state)
  # Adding a new undo step clears the redo history
  # getObjectByName('undoButton').enable()
  # getObjectByName('redoButton').disable()

def undo():
  """Go back one step in the history"""
  if not undoHistory:
    return
  createRedoHistory()
  newState = undoHistory.pop()
  if not undoHistory:
    getObjectByName('undoButton').disable()
  purgeScene()
  deserializeScene(newState)
  getObjectByName('redoButton').enable()

def redo():
  """Go forward one step in the undo history"""
  if not redoHistory:
    return
  createUndoHistory(False)
  newState = redoHistory.popleft()
  if not redoHistory:
    getObjectByName('redoButton').disable()
  purgeScene()
  deserializeScene(newState)
  getObjectByName('undoButton').enable()

def setWindowTitle(newTitle, star=True):
  """Set the window title"""
  s = 'Mayday Level Editor - %s%s' % (newTitle, '*' if star else '')
  pygame.display.set_caption(s)

def getObjectByName(name):
  """Identify objects having unique names"""
  result = [o for o in objectsList if o.name==name]
  if not result:
    raise IndexError('Objectslist contains no object named "%s"!' % name)
  elif len(result) > 1:
    raise IndexError('Objectslist contains multiple objects named "%s"!' % name)
  return result[0]

def getObjectsByClass(cls):
  """Identify objects by their class"""
  result = [o for o in objectsList if isinstance(o, cls)]
  if not result:
    raise IndexError('Objectslist contains no object of class "%s"!' % cls.__name__)
  return result

def compute_projection_parameters(newazimuth, newelevation, newzoom):
  """Changes the camera perspective"""
  global azimuth, elevation, right, front, up, zoom
  azimuth = newazimuth
  while azimuth < 0.: azimuth += 2*pi
  while azimuth > 2*pi: azimuth -= 2*pi
  elevation = min(0., max(-pi, newelevation))
  right = [cos(azimuth), sin(azimuth) * cos(elevation)]
  front = [sin(azimuth), -cos(azimuth) * cos(elevation)]
  up = [0, sin(elevation)]
  zoom = min(10., max(0.1, newzoom))


def project3dToPixelPosition(c, origin=ORIGIN):
  """Computes the 2D pixel screen coordinate for a 3D point"""
  # Isometric projection
  #          [ -right- ]T    [ | ]
  # result = [ -front- ]  *  [ c ]
  #          [ --up--- ]     [ | ]
  result = [c.x * right[0] + c.y * front[0] + c.z * up[0],
            c.x * right[1] + c.y * front[1] + c.z * up[1]]
  result[0] *= zoom
  result[1] *= zoom
  # Compensate for pixel shift (window center is world center)
  result[0] += origin[0]
  result[1] += origin[1]
  return result


def unprojectPixelTo3dPosition(p, origin=ORIGIN, height=0.):
  """Computes the 3d coordinates for a 2d pixel position, given a (z-) height"""
  # Yes, this is ugly, but the math is VERY simple: Just resolve the system
  # used in project3dToPixelPosition() to compute the pixel, and the fact
  # that the height (=z) is known.
  #
  # p[0] = (x*right[0] + y*front[0] + z*up[0])*zoom + origin[0]
  # p[1] = (x*right[1] + y*front[1] + z*up[1])*zoom + origin[1]
  #
  # There are three variables (x,y,z), but only two equations. That is why the
  # function parameter HEIGHT is necessary to get an overdetermined system.
  # (The ORIGIN is assumed to be constant.)
  y = ((p[1]-origin[1])/(zoom*front[1]) -                                \
        height*up[1]/front[1] -                                          \
       (right[1]/(right[0]*front[1]))*                                   \
       ((p[0]-origin[0])/zoom - height*up[0])) /                         \
      (1. - (front[0]*right[1])/(right[0]*front[1]))
  x = ((p[0]-origin[0])/zoom - height*up[0] - y*front[0]) / right[0]
  z = height
  point3d = Point3D(x, y, z)
  return point3d


def drawPotentialConnectionLine(p1, p2, screen):
  # Yes, this is really not how that was intended to be used.
  s = Straight(p1,p2)
  s.draw(screen)


def drawHelpLines(pos3D, screen, toOrigin=True):
  """Draw 3D orientation help lines"""
  positions = [project3dToPixelPosition(Point3D(0, 0, 0)),
               project3dToPixelPosition(Point3D(pos3D.x, 0, 0)),
               project3dToPixelPosition(Point3D(pos3D.x, pos3D.y, 0)),
               project3dToPixelPosition(pos3D)]
  min_x = int(min([p[0] for p in positions]))
  max_x = int(max([p[0] for p in positions]))
  min_y = int(min([p[1] for p in positions]))
  max_y = int(max([p[1] for p in positions]))
  start = positions[0]
  end = positions[-1]
  # Safely overestimate the needed area (pad to avoid clipping lines)
  tempSurfaceObj = pygame.Surface((2*max([abs(max_x-start[0]),
                                          abs(min_x-start[0])])+5,
                                   2*max([abs(max_y-start[1]),
                                          abs(min_y-start[1])])+5))
  tempSurfaceObj = tempSurfaceObj.convert_alpha()
  tempSurfaceObjCenter = [tempSurfaceObj.get_size()[0]//2,
                          tempSurfaceObj.get_size()[1]//2]
  line_anchors = [tempSurfaceObjCenter]
  # Draw a path from the origin along the 3 dimensions
  for i in range(3):
    color = (0, 0, 0, 0)
    if toOrigin:
      color = (0, 0, 127)
    else:
      color = (127, 127, 127)
    line_anchors.append((positions[i+1][0]-start[0]+tempSurfaceObjCenter[0],
                         positions[i+1][1]-start[1]+tempSurfaceObjCenter[1]))
    pygame.draw.aaline(tempSurfaceObj, color,
                       line_anchors[i], line_anchors[i+1])
  # Repair the alpha values (transparency) at antialiasing border
  pixels = pygame.PixelArray(tempSurfaceObj)
  pixels.replace(pygame.Color(0, 0, 0, 255), pygame.Color(0, 0, 0, 0))
  del pixels
  # Draw
  tempSurfaceObjRect = tempSurfaceObj.get_rect()
  tempSurfaceObjRect.center = ORIGIN
  screen.blit(tempSurfaceObj, tempSurfaceObjRect)


def render_background():
  "Rerender the 'ground' (z=0 plane) grid"
  # Create and fill background
  BGSurfaceObj = pygame.Surface(WINDOW_SIZE)
  BGSurfaceObj.fill((200,200,255))
  # Render grid lines
  for i in range(21):
    pygame.draw.aaline(BGSurfaceObj, (255,255,255),
                       project3dToPixelPosition(Point3D((i-10)*50,-500, 0)),
                       project3dToPixelPosition(Point3D((i-10)*50, 500, 0)))
    pygame.draw.aaline(BGSurfaceObj, (255,255,255),
                       project3dToPixelPosition(Point3D(-500, (i-10)*50, 0)),
                       project3dToPixelPosition(Point3D( 500, (i-10)*50, 0)))
  return BGSurfaceObj


def makeGUIButtons():
  """Initialize GUI buttons"""
  buttons = []
  to_make = ((NewSceneButton, "newSceneButton",
                (50, 0)),
             (LoadSceneButton, "loadSceneButton",
                (50, 50)),
             (SaveSceneButton, "saveSceneButton",
                (50, 100)),
             (ExitProgramButton, "exitProgramButton",
                (50, 150)),
             (AddStraightButton, "addStraightButton",
                (WINDOW_SIZE[0], 0)),
             (AppendStraightButton, "appendStraightButton",
                (WINDOW_SIZE[0]-50, 0)),
             (AddHelixArcButton, "addHelixArcButton",
                (WINDOW_SIZE[0], 50)),
             (AppendHelixArcButton, "appendHelixArcButton",
                (WINDOW_SIZE[0]-50, 50)),
             (ChangeActiveEndButton, "changeActiveEndButton",
                (WINDOW_SIZE[0], 100)),
             (DeleteObjectsButton, "deleteObjectsButton",
                (WINDOW_SIZE[0], 150)),
             (UndoButton, "undoButton",
                (WINDOW_SIZE[0]//2,0)),
             (RedoButton, "redoButton",
                (WINDOW_SIZE[0]//2+50,0))
            )

  for buttonClass, name, (x,y) in to_make:
    newButton = buttonClass(name)
    rect = newButton.surfaceObj.get_rect()
    rect.topright = (x,y)
    newButton.setRectangle(rect)
    buttons.append(newButton)

  global objectsList
  objectsList.extend(buttons)
  getObjectByName("appendStraightButton").disable()
  getObjectByName("appendHelixArcButton").disable()
  getObjectByName("deleteObjectsButton").disable()
  getObjectByName("undoButton").disable()
  getObjectByName("redoButton").disable()



def infoMessage(msg):
  """Append a message to the queue and keep the queue at a max length"""
  global messageQueue, messageQueueChange
  messageQueueChange = True
  messageQueue.append(msg)
  while len(messageQueue) > 8:
    messageQueue.popleft()



def deselectObjects(obj=None):
  global selectedObjects
  if obj is None:
    for o in selectedObjects:
      o.deselect()
    selectedObjects = []
  else:
    if isinstance(obj, list):
      for newObject in obj:
        if newObject in selectedObjects:
          selectedObjects.remove(newObject)
          newObject.deselect()
          infoMessage("Object deselected.")
    elif obj in selectedObjects:
      selectedObjects.remove(obj)
      obj.deselect()
      infoMessage("Object deselected.")



def selectObjects(obj=None):
  global selectedObjects, idleClick
  idleClick = False
  if obj is not None:
    if isinstance(obj, list):
      for newObject in obj:
        if newObject not in selectedObjects:
          selectedObjects.append(newObject)
          newObject.select()
    elif obj not in selectedObjects:
      selectedObjects.append(obj)
      obj.select()



def discardDeprecatedSelections(rect):
  for o in selectedObjects:
    if not o.inRect(rect):
      deselectObjects(o)




def deleteObject(obj):
  deselectObjects(obj)
  obj.deselect()
  objectsList.remove(obj)



def drawHelpDebugInfoMessages(screen, rerender=False,
                              msgs1=[], msgs2=[], msgq=[]):
  """
  Draw helpful texts and print the info message queue.
  WARNING: msgs1, msgs2 and msgq use Python's mutable default arguments
           functionality.
           DO NOT set them manually or use them in a function call!
  """
  global messageQueueChange

  for so in selectedObjects:
    pos = so.center
    ppos = project3dToPixelPosition(pos)
    # Render info text at (and about) position (3D -> pixels)
    text = '(%.1f, %.1f, %.1f) -> (%d, %d)'%(pos.x, pos.y, pos.z,
                                             ppos[0], ppos[1])
    textObj = pygame.font.SysFont(None, 18).render(text, True, (0, 0, 0))
    textRect = textObj.get_rect()
    textRect.topleft = (ppos[0]+10, ppos[1])
    screen.blit(textObj, textRect)

  # Render info text about azimuth and elevation angles
  if rerender or not msgs1:
    # Change list in-place. "msgs1=[]" would not work, because with the next
    # function call msgs1 would again be empty.
    msgs1[:] = []
    lines = ["azimuth angle = %.2f RAD (ca. %d DEG)" % (azimuth, azimuth*180./pi),
             "Elevation angle = %.2f RAD (ca. %d DEG)" % (elevation, elevation*180./pi),
             "Zoom factor = %.2f" % zoom]
    for i in range(3):
      textObj = pygame.font.SysFont(None, 18).render(lines[i], True, (0, 0, 0))
      textRect = textObj.get_rect()
      textRect.topleft = (60, (i+1)*15)
      msgs1.append((textObj, textRect))

  # Some help text
  if not msgs2:
    lines = ["Use WASD or MIDDLE MOUSE BUTTON to rotate the camera (isometric projection).",
             "Move selected objects with the ARROW KEYS and PAGE-UP/DOWN, or drag them",
             "  using the mouse (hold SHIFT to move along the z-axis).",
             "Zoom in and out using the +/- keys, RIGHT MOUSE BUTTON or MOUSE WHEEL.",
             "Press HOME to reset the camera.",
             "Ctrl+A selects all objects."][::-1]
    for i in range(len(lines)):
      textObj = pygame.font.SysFont(None, 18).render(lines[i], True, (0, 0, 0))
      textRect = textObj.get_rect()
      textRect.topleft = (0, WINDOW_SIZE[1]-(i+1)*15)
      msgs2.append((textObj, textRect))

  # Print the info messages from messageQueue
  if messageQueueChange or not msgq:
    messageQueueChange = False
    msgq[:] = []
    for i, m in enumerate(messageQueue):
      textObj = pygame.font.SysFont(None, 18).render(messageQueue[i], True, (0, 0, 0))
      textRect = textObj.get_rect()
      textRect.topright = (WINDOW_SIZE[0]-5, WINDOW_SIZE[1]-(i+1)*15)
      msgq.append((textObj, textRect))

  for l in (msgs1, msgs2, msgq):
    for text, rect in l:
      screen.blit(text, rect)


def markObject(obj, screen):
  markersize = 15
  marker = pygame.Surface(obj.rect.size)
  marker = marker.convert_alpha()
  pointslist = [(min(markersize, obj.rect.width-1), 0),
                (0, 0),
                (0, min(markersize, obj.rect.height-1))]
  pygame.draw.lines(marker, (255, 255, 255), False, pointslist, 1)
  pointslist = [(obj.rect.width-1 - min(markersize, obj.rect.width-1), 0),
                (obj.rect.width-1, 0),
                (obj.rect.width-1, min(markersize, obj.rect.height-1))]
  pygame.draw.lines(marker, (255, 255, 255), False, pointslist, 1)
  pointslist = [(min(markersize, obj.rect.width-1), obj.rect.height-1),
                (0, obj.rect.height-1),
                (0, obj.rect.height-1 - min(markersize, obj.rect.height-1))]
  pygame.draw.lines(marker, (255, 255, 255), False, pointslist, 1)
  pointslist = [(obj.rect.width-1 - min(markersize, obj.rect.width-1), obj.rect.height-1),
                (obj.rect.width-1, obj.rect.height-1),
                (obj.rect.width-1, obj.rect.height-1 - min(markersize, obj.rect.height-1))]
  pygame.draw.lines(marker, (255, 255, 255), False, pointslist, 1)
  pixels = pygame.PixelArray(marker)
  pixels.replace(pygame.Color(0, 0, 0, 255), pygame.Color(0, 0, 0, 0))
  del pixels
  screen.blit(marker, obj.rect)


#_______________________________________________________________________


def main():
  global idleClick, objectsList, selectedObjects

  logging.basicConfig(level=logging.DEBUG,
                      format='%(asctime)s %(levelname)s: %(message)s',
                      stream=sys.stdout)

  # Initialize pygame
  pygame.init()
  screen = pygame.display.set_mode(WINDOW_SIZE)

  # Set window icon
  # Image credit: http://chidioparareports.blogspot.de/2012/06/special-report-nigerian-airlines-and.html
  icon = pygame.image.load('{}/img/icon.png'.format(SCRIPT_PATH))
  pygame.display.set_icon(icon)

  # Set window title
  setWindowTitle("New Scene")

  # Make mouse visible
  pygame.mouse.set_visible(1)

  # Create clock object used to limit the framerate
  clock = pygame.time.Clock()
  # Repeat keypresses as long as the are held down (=resending events?)
  pygame.key.set_repeat(1, 30)

  # Render the initial background ("floor" grid)
  BGSurfaceObj = render_background()

  # Create GUI buttons
  makeGUIButtons()

  # Prerender the marker for a path piece's active end
  global markring, markdot, markrectangle
  markring      = markring.convert_alpha()
  markdot       = markdot.convert_alpha()
  markrectangle = markrectangle.convert_alpha()
  markring.fill((0,0,0,0))
  markdot.fill((0,0,0,0))
  markrectangle.fill((0,0,0,0))
  for dx,dy in MARK_RING_OFFSETS:
    markring.set_at((CLICK_TOLERANCE_RADIUS+dx,
                     CLICK_TOLERANCE_RADIUS+dy),
                    (255,0,0))
  for dx,dy in MARK_DOT_OFFSETS:
    markdot.set_at((CLICK_TOLERANCE_RADIUS+dx,
                    CLICK_TOLERANCE_RADIUS+dy),
                   (255,0,0))
  for i in range(2*CLICK_TOLERANCE_RADIUS+1):
    markrectangle.set_at((i, 0),
                         (255, 0, 0))
    markrectangle.set_at((0, i),
                         (255, 0, 0))
    markrectangle.set_at((i, 2*CLICK_TOLERANCE_RADIUS),
                         (255, 0, 0))
    markrectangle.set_at((2*CLICK_TOLERANCE_RADIUS, i),
                         (255, 0, 0))

  # Prerender the button tooltips
  for k, v in TOOLTIP_TEXTS.items():
    tmp = pygame.font.SysFont(None, 20).render(v, True, (0,0,0), (255,255,255))
    TOOLTIP_SURFACEOBJECTS[k] = tmp

  # How far the mouse has travelled with a button down, used to distinguish
  # between "click" and "drag" actions
  dragManhattanDistance = 0
  # Mouse status saved from previous timetick
  lmbLastTick = mmbLastTick = rmbLastTick = False
  # Used for moving objects
  boxSelectionInProgress = dragStartedOnGUI                 \
                         = dragStartedOnSelectedObject      \
                         = dragStartedOnActiveEnd           \
                         = dragStartedOnInactiveEnd         \
                         = dragStartedOnBezierControlStart  \
                         = dragStartedOnBezierControlEnd    \
                         = False
  boxStartPoint = (0, 0)

  # Print info and debugging text?
  printDebug = False

  # Occasionally render HelixArcs in high quality
  framesWithoutRerendering = 0

  ### DEBUG
  """objectsList.append(HelixArc(startHeight=-40., endHeight=140.,
                               startAngle=180., endAngle=360.,
                               radius=50., center=Point3D(),
                               rightHanded=True, color=(0,0,255),
                               gamma=1.))
  objectsList.append(HelixArc(startHeight=20., endHeight=140.,
                               startAngle=-360., endAngle=360.,
                               radius=100., center=Point3D(0,100,0),
                               rightHanded=False, color=(0,0,255),
                               gamma=1.))"""
  objectsList.append(BezierArc(startPoint3D=Point3D(100,0,-50),
                               endPoint3D=Point3D(-100,0,50),
                               bezierControlStartPoint3D=Point3D(0,50,0),
                               bezierControlEndPoint3D=Point3D(0,-50,0)))

  # Prerender font object
  toggleDebugTextObj = pygame.font.SysFont(None, 18).render('Press H to toggle debug information.',
                                                            True, (0,0,0))

  # Global frame counter
  totalFrameCount = 0

  pressedKeysLastTick = None

  # MAIN LOOP
  running = True
  while running:
    # Limit to 30 fps
    clock.tick(30)

    totalFrameCount += 1

    # pygame.mouse.get_pressed() only works after depleting the event queue
    thisTickEvents = pygame.event.get()

    # Performance trick: Don't do ANYTHING unless something happens!
    # NOTE that even mouse movement within the game window is an event.
    #
    # (totalFrameCount > HelixArc._HQFrameDelay) is a hack to ensure that the
    # first few frames are rendered even if no events occur
    if not pygame.event.peek() and \
       totalFrameCount > HelixArc._HQFrameDelay and \
       not framesWithoutRerendering < 3:
      thisTickEvents.append(pygame.event.wait())

    # Check current status of mouse buttons (not events)
    lmbDown, mmbDown, rmbDown = pygame.mouse.get_pressed()

    # Get relative mouse movement since the last timetick
    mouseRelativeMotionThisTick = pygame.mouse.get_rel()
    mousePos = pygame.mouse.get_pos()

    # Update dragManhattanDistance if the button status has not changed since last tick
    if (lmbDown and lmbLastTick) or \
       (mmbDown and mmbLastTick) or \
       (rmbDown and rmbLastTick):
      dragManhattanDistance += abs(mouseRelativeMotionThisTick[0]) + \
                               abs(mouseRelativeMotionThisTick[1])
    elif lmbDown or mmbDown or rmbDown:
      dragManhattanDistance = 0

    # Initiate box selection
    if lmbDown and \
       dragManhattanDistance > DRAGGING_DISTANCE_THRESHOLD and \
       not boxSelectionInProgress           and \
       not dragStartedOnGUI                 and \
       not dragStartedOnSelectedObject      and \
       not dragStartedOnActiveEnd           and \
       not dragStartedOnInactiveEnd         and \
       not dragStartedOnBezierControlStart  and \
       not dragStartedOnBezierControlEnd:
      deselectObjects()
      boxSelectionInProgress = True
      boxStartPoint = pygame.mouse.get_pos()

    # Significant mouse motion while a button is pressed
    if dragManhattanDistance > DRAGGING_DISTANCE_THRESHOLD:
      idleClick = False

    # Objects may need to be rerendered if camera parameters change
    rerender = False

    # Process event queue
    for event in thisTickEvents:
      # Quit game
      if event.type == pygame.QUIT:
        running = False
      # Quit game with ESC key
      # elif event.type == pygame.KEYDOWN:
        # if event.key == pygame.K_ESCAPE:
          # logging.debug("Quitting (ESC key)")
          # running = False
      # A mouse button was clicked
      elif event.type == pygame.MOUSEBUTTONDOWN:
        # Buttons 1-3 are LMB, MMB, RMB
        if event.button < 4:
          idleClick = True
          # LMB click activates GUI elements, selects objects
          if lmbDown:
            GUIwasClicked = False
            for o in objectsList:
              if isinstance(o, Button) and o.cursorOnObject(mousePos):
                GUIwasClicked = True
                dragStartedOnGUI = True
                infoMessage("dragStartedOnGUI")
                o.activate()
                o.clickAction()
            if not GUIwasClicked:
              if len(selectedObjects)==1:
                if selectedObjects[0].cursorOnObject():
                  so = selectedObjects[0]
                  if so.cursorOnEnd(mousePos):
                    createUndoHistory()
                    dragStartedOnActiveEnd = True
                  elif so.cursorOnEnd(mousePos, False):
                    createUndoHistory()
                    dragStartedOnInactiveEnd = True
                  else:
                    createUndoHistory()
                    dragStartedOnSelectedObject = True
                    infoMessage("dragStartedOnSelectedObject")
                  break
                elif isinstance(so, BezierArc):
                  if so.cursorOnBezierControl(mousePos):
                    createUndoHistory()
                    dragStartedOnBezierControlStart = True
                  elif so.cursorOnBezierControl(mousePos, False):
                    createUndoHistory()
                    dragStartedOnBezierControlEnd = True
              else:
                for so in selectedObjects:
                  if so.cursorOnObject(mousePos):
                    createUndoHistory()
                    dragStartedOnSelectedObject = True
                    infoMessage("dragStartedOnSelectedObject")
                    break
        # Button 4 is MOUSE WHEEL UP
        elif event.button == 4:
          compute_projection_parameters(azimuth, elevation, zoom*ZOOM_IN_SPEED**2)
          rerender = True
        # Button 5 is MOUSE WHEEL DOWN
        elif event.button == 5:
          compute_projection_parameters(azimuth, elevation, zoom*ZOOM_OUT_SPEED**2)
          rerender = True
        else:
          raise Exception('Unknown mouse button %d!' % event.button)
      # Button up
      elif event.type == pygame.MOUSEBUTTONUP:
        # If the click was idle, forget the preemptively created history point
        if (dragStartedOnActiveEnd              or \
            dragStartedOnInactiveEnd            or \
            dragStartedOnSelectedObject         or \
            dragStartedOnBezierControlStart     or \
            dragStartedOnBezierControlEnd)     and \
            idleClick:
            undoHistory.pop()
            if not undoHistory:
              getObjectByName('undoButton').disable()
        if lmbLastTick                          and \
           not boxSelectionInProgress           and \
           not dragStartedOnGUI                 and \
           not dragStartedOnActiveEnd           and \
           not dragStartedOnBezierControlStart  and \
           not dragStartedOnBezierControlEnd    and \
           not dragStartedOnInactiveEnd:
          deselectObjects()
        # Only "click"-select objects (box selection is done later)
        if not boxSelectionInProgress           and \
           not dragStartedOnActiveEnd           and \
           not dragStartedOnBezierControlStart  and \
           not dragStartedOnBezierControlEnd    and \
           not dragStartedOnInactiveEnd:
          for o in objectsList:
            if o.cursorOnObject(mousePos) and not isinstance(o, Button):
              selectObjects(o)
              infoMessage("Object selected (via Click).")
              # Click-selection can only select one object at a time
              # TODO ordering/preference?
              break
          for o in objectsList:
            if isinstance(o, Button):
              o.deactivate()
        # Clicking into nothing is common for "cancel everything"
        if idleClick and lmbLastTick:
          infoMessage("Idle lMB click, deselecting all...")
          deselectObjects()
        # Reset drag distance
        dragManhattanDistance = 0
        boxSelectionInProgress = dragStartedOnGUI                 \
                               = dragStartedOnSelectedObject      \
                               = dragStartedOnActiveEnd           \
                               = dragStartedOnInactiveEnd         \
                               = dragStartedOnBezierControlStart  \
                               = dragStartedOnBezierControlEnd    \
                               = False

    # Check current status of keyboard keys
    pressedKeys = pygame.key.get_pressed()

    if pressedKeys[pygame.K_h] and not pressedKeysLastTick[pygame.K_h]:
      printDebug = not printDebug
    # Change camera settings using keyboard
    if pressedKeys[pygame.K_a] and not \
       pressedKeys[pygame.K_LCTRL] or pressedKeys[pygame.K_RCTRL]:
      compute_projection_parameters(azimuth-AZIMUTH_ANGULAR_SPEED, elevation, zoom)
      rerender = True
    if pressedKeys[pygame.K_d]:
      compute_projection_parameters(azimuth+AZIMUTH_ANGULAR_SPEED, elevation, zoom)
      rerender = True
    if pressedKeys[pygame.K_w]:
      compute_projection_parameters(azimuth, elevation+ELEVATION_ANGULAR_SPEED, zoom)
      rerender = True
    if pressedKeys[pygame.K_s] and not \
       pressedKeys[pygame.K_LCTRL] or pressedKeys[pygame.K_RCTRL]:
      compute_projection_parameters(azimuth, elevation-ELEVATION_ANGULAR_SPEED, zoom)
      rerender = True
    if pressedKeys[pygame.K_HOME]:
      compute_projection_parameters(315*(pi/180.), -66*(pi/180.), 1.0)
      rerender = True
    if pressedKeys[pygame.K_MINUS]:
      compute_projection_parameters(azimuth, elevation, zoom*ZOOM_OUT_SPEED)
      rerender = True
    if pressedKeys[pygame.K_PLUS]:
      compute_projection_parameters(azimuth, elevation, zoom*ZOOM_IN_SPEED)
      rerender = True

    ## Change camera settings using mouse
    # azimuth and Elevation angles
    if dragManhattanDistance > DRAGGING_DISTANCE_THRESHOLD:
      if mmbDown:
        if mouseRelativeMotionThisTick[0] != 0 or \
           mouseRelativeMotionThisTick[1] != 0:
          compute_projection_parameters(azimuth-AZIMUTH_ANGULAR_SPEED*
                                                 mouseRelativeMotionThisTick[0]*
                                                 MOUSE_AZIMUTH_ANGULAR_SPEED,
                                        elevation+ELEVATION_ANGULAR_SPEED*
                                                  mouseRelativeMotionThisTick[1]*
                                                  MOUSE_ELEVATION_ANGULAR_SPEED,
                                        zoom)
          rerender = True
      # Zoom factor
      if rmbDown:
        if mouseRelativeMotionThisTick[1] < 0:
          compute_projection_parameters(azimuth,
                                        elevation,
                                        zoom*ZOOM_IN_SPEED**
                                          (-mouseRelativeMotionThisTick[1]*
                                            MOUSE_ZOOM_IN_SPEED))
          rerender = True
        if mouseRelativeMotionThisTick[1] > 0:
          compute_projection_parameters(azimuth,
                                        elevation,
                                        zoom*ZOOM_OUT_SPEED**
                                          (mouseRelativeMotionThisTick[1]*
                                           MOUSE_ZOOM_OUT_SPEED))
          rerender = True

    ## Keyboard shortcuts
    if pressedKeysLastTick != pressedKeys:
      if pressedKeys[pygame.K_LCTRL] or pressedKeys[pygame.K_RCTRL]:
        # Ctrl+A: Select all objects
        if pressedKeys[pygame.K_a] and not pressedKeysLastTick[pygame.K_a]:
          infoMessage("Select all")
          for o in objectsList:
            if not isinstance(o, Button):
              selectObjects(o)
        # Ctrl-Z: Undo
        if pressedKeys[pygame.K_z]:
          undo()
        # Ctrl-Y: Redo
        if pressedKeys[pygame.K_y]:
          redo()
        # Ctrl-N: New scene
        if pressedKeys[pygame.K_n]:
          getObjectByName('newSceneButton').clickAction(True)
        # Ctrl-O: Load scene
        if pressedKeys[pygame.K_o]:
          getObjectByName('loadSceneButton').clickAction(True)
        # Ctrl-S: Save scene
        if pressedKeys[pygame.K_s]:
          getObjectByName('saveSceneButton').clickAction(True)
        # Ctrl-Q: Quit program
        if pressedKeys[pygame.K_q]:
          getObjectByName('exitProgramButton').clickAction(True)

    """# Move selected objects per keyboard
    try:
      for so in selectedObjects:
        if pressedKeys[pygame.K_UP]:
          so.moveByOffset((0,10,0))
        if pressedKeys[pygame.K_DOWN]:
          so.moveByOffset((0,-10,0))
        if pressedKeys[pygame.K_LEFT]:
          so.moveByOffset((-10,0,0))
        if pressedKeys[pygame.K_RIGHT]:
          so.moveByOffset((10,0,0))
        if pressedKeys[pygame.K_PAGEUP]:
          so.moveByOffset((0,0,10))
        if pressedKeys[pygame.K_PAGEDOWN]:
          so.moveByOffset((0,0,-10))
    except:
      for so in selectedObjects: print so"""

    ## Delete selected objects
    if pressedKeys[pygame.K_DELETE] and selectedObjects:
      getObjectByName('deleteObjectsButton').clickAction(True)

    # Change a HelixArc's curve gamma
    if len(selectedObjects)==1 and isinstance(selectedObjects[0], HelixArc):
      so = selectedObjects[0]
      if pressedKeys[pygame.K_m]:
        so.recompute()
        so.render(True)
        so.gamma *= 1.05
        so.gamma = max(.05, min(9., so.gamma))
      elif pressedKeys[pygame.K_n]:
        so.recompute()
        so.render(True)
        so.gamma *= .96
        so.gamma = max(.05, min(9., so.gamma))

    ## Move things using the mouse
    if dragManhattanDistance > DRAGGING_DISTANCE_THRESHOLD:
      # Move selected object(s)
      if dragStartedOnSelectedObject:
        # Motion along z-axis
        if pressedKeys[pygame.K_RSHIFT] or pressedKeys[pygame.K_LSHIFT]:
          for so in selectedObjects:
            so.moveTo(Point3D(so.center.x,
                              so.center.y,
                              so.center.z-mouseRelativeMotionThisTick[1]))
        # Motion along (z=0)-plane
        else:
          for so in selectedObjects:
            so.moveByPixelOffset(mouseRelativeMotionThisTick)
      # Manipulate a single selected object
      elif len(selectedObjects)==1:
        so = selectedObjects[0]
        # Move the ends of a path piece using the mouse
        ## HelixArcs
        if isinstance(so, HelixArc):
          if dragStartedOnActiveEnd or dragStartedOnInactiveEnd:
            # Change a HelixArc's RADIUS using the SHIFT+CTRL keys
            if (pressedKeys[pygame.K_RSHIFT] or pressedKeys[pygame.K_LSHIFT]) and \
               (pressedKeys[pygame.K_LCTRL]  or pressedKeys[pygame.K_RCTRL]):
              so.radius += mouseRelativeMotionThisTick[0]
              so.recompute()
              so.render(True)
            # Change a HelixArc's HEIGHT using the SHIFT key
            elif pressedKeys[pygame.K_RSHIFT] or pressedKeys[pygame.K_LSHIFT]:
              pos = so.getEndPoint3d(dragStartedOnActiveEnd)
              pos = Point3D(pos.x,
                            pos.y,
                            pos.z-mouseRelativeMotionThisTick[1])
              so.setEndPos3d(pos, dragStartedOnActiveEnd)
            # Change a HelixArc's LENGTH using the CTRL key
            elif pressedKeys[pygame.K_LCTRL] or pressedKeys[pygame.K_RCTRL]:
              so.changeAngles(mouseRelativeMotionThisTick,
                              dragStartedOnActiveEnd)
        ## BezierArcs
        if isinstance(so, BezierArc):
          if dragStartedOnActiveEnd or dragStartedOnInactiveEnd:
            # Change a BezierArc's HEIGHT using the SHIFT key
            if pressedKeys[pygame.K_RSHIFT] or pressedKeys[pygame.K_LSHIFT]:
              pos = so.getEndPoint3d(dragStartedOnActiveEnd)
              pos = Point3D(pos.x,
                            pos.y,
                            pos.z-mouseRelativeMotionThisTick[1])
              so.setEndPos3d(pos, dragStartedOnActiveEnd)
            else:
              pos = so.getEndPoint3d(dragStartedOnActiveEnd)
              z = pos.z
              ppos = project3dToPixelPosition(pos)
              ppos[0] += mouseRelativeMotionThisTick[0]
              ppos[1] += mouseRelativeMotionThisTick[1]
              pos = unprojectPixelTo3dPosition(ppos, ORIGIN, z)
              so.setEndPos3d(pos, dragStartedOnActiveEnd)
          elif dragStartedOnBezierControlStart or dragStartedOnBezierControlEnd:
            # Change a BezierArc's control points
            # Along the z axis
            if pressedKeys[pygame.K_RSHIFT] or pressedKeys[pygame.K_LSHIFT]:
              pos = so.getBezierControl(dragStartedOnBezierControlStart)
              pos = Point3D(pos.x,
                            pos.y,
                            pos.z-mouseRelativeMotionThisTick[1])
              so.setBezierControl(pos, dragStartedOnBezierControlStart)
            # Within the xy plane
            else:
              pos = so.getBezierControl(dragStartedOnBezierControlStart)
              z = pos.z
              ppos = project3dToPixelPosition(pos)
              ppos[0] += mouseRelativeMotionThisTick[0]
              ppos[1] += mouseRelativeMotionThisTick[1]
              pos = unprojectPixelTo3dPosition(ppos, ORIGIN, z)
              so.setBezierControl(pos, dragStartedOnBezierControlStart)
        ## Straights
        elif isinstance(so, Straight):
          if dragStartedOnActiveEnd or dragStartedOnInactiveEnd:
            # Move endpoint along z-axis
            if pressedKeys[pygame.K_RSHIFT] or pressedKeys[pygame.K_LSHIFT]:
              pos = so.getEndPoint3d(dragStartedOnActiveEnd)
              pos = Point3D(pos.x,
                            pos.y,
                            pos.z-mouseRelativeMotionThisTick[1])
              so.setEndPos3d(pos, dragStartedOnActiveEnd)
            #elif pressedKeys[pygame.K_RCTRL] or pressedKeys[pygame.K_LCTRL]:
            else:
              pos = so.getEndPoint3d(dragStartedOnActiveEnd)
              z = pos.z
              ppos = project3dToPixelPosition(pos)
              ppos[0] += mouseRelativeMotionThisTick[0]
              ppos[1] += mouseRelativeMotionThisTick[1]
              pos = unprojectPixelTo3dPosition(ppos, ORIGIN, z)
              so.setEndPos3d(pos, dragStartedOnActiveEnd)



    # If the camera has changed, the background graphic has to be re-rendered
    if rerender:
      framesWithoutRerendering = 0
      BGSurfaceObj = render_background()
      for o in objectsList:
        o.render()
    else:
      framesWithoutRerendering += 1

    # Render HelixArcs in good quality if the scene is stationary
    if framesWithoutRerendering == HelixArc._HQFrameDelay:
      infoMessage("Rendering HelixArcs in HD...")
      for o in objectsList:
        if isinstance(o, HelixArc):
          o.render(True)

    # Save keyboard state for next tick
    pressedKeysLastTick = pressedKeys

    # DRAWING
    screen.blit(BGSurfaceObj, (0, 0))

    # Draw help lines to ease positioning selected objects in 3D space
    for so in selectedObjects:
      drawHelpLines(so.center, screen)
      if isinstance(so, Straight):
        drawHelpLines(so.getEndPoint3d(True), screen, False)
        drawHelpLines(so.getEndPoint3d(False), screen, False)
      elif isinstance(so, HelixArc):
        drawHelpLines(so.getEndPoint3d(True) + so.center,
                      screen,
                      False)
        drawHelpLines(so.getEndPoint3d(False) + so.center,
                      screen,
                      False)

    # Print helpful information and debugging messages (CPU intensive!)
    textRect = toggleDebugTextObj.get_rect()
    textRect.topleft = (60,0)
    screen.blit(toggleDebugTextObj, textRect)
    if printDebug:
      drawHelpDebugInfoMessages(screen, rerender)

    # Draw objects
    for o in objectsList:
      o.draw(screen)

    # Draw the selection box and select objects whose centers are within the box
    if boxSelectionInProgress:
      boxEndPoint = pygame.mouse.get_pos()
      minx = min(boxStartPoint[0], boxEndPoint[0])
      maxx = max(boxStartPoint[0], boxEndPoint[0])
      miny = min(boxStartPoint[1], boxEndPoint[1])
      maxy = max(boxStartPoint[1], boxEndPoint[1])
      selectionBox = pygame.Surface((maxx-minx, maxy-miny))
      selectionBox.fill((150,150,255))
      pointslist = [(0,0),(maxx-minx-1,0),(maxx-minx-1,maxy-miny-1),(0,maxy-miny-1)]
      pygame.draw.lines(selectionBox, (0, 0, 255), True, pointslist, 1)
      selectionBox.set_alpha(100)
      selectionBoxRect = selectionBox.get_rect()
      selectionBoxRect.center = [.5*(boxStartPoint[0]+boxEndPoint[0]),
                                 .5*(boxStartPoint[1]+boxEndPoint[1])]
      screen.blit(selectionBox, selectionBoxRect)
      # deselectObjects()
      discardDeprecatedSelections(selectionBoxRect)
      for obj in objectsList:
        if obj.inRect(selectionBoxRect) and not isinstance(obj, Button):
          if not obj.selected:
            infoMessage("Object selected (via Box).")
          selectObjects(obj)

    # Visualize selected objects with a box
    for o in selectedObjects:
      markObject(o, screen)

    # Update buttons
    # TODO refactor into Button method?
    if not selectedObjects or len(selectedObjects) != 1:
      getObjectByName('appendStraightButton').disable()
      getObjectByName('appendHelixArcButton').disable()
      getObjectByName('changeActiveEndButton').disable()
    else:
      getObjectByName('appendStraightButton').enable()
      getObjectByName('appendHelixArcButton').enable()
      getObjectByName('changeActiveEndButton').enable()

    if not selectedObjects:
      getObjectByName('deleteObjectsButton').disable()
    else:
      getObjectByName('deleteObjectsButton').enable()

    # Draw GUI buttons
    for o in objectsList:
      if isinstance(o, Button):
        if o.cursorOnObject(mousePos) and \
           not dragManhattanDistance > DRAGGING_DISTANCE_THRESHOLD :
          o.highlight()
          o.draw(screen)
          o.dehighlight()
        else:
          o.draw(screen)

    # Draw GUI tooltips (after drawing all buttons -> tooltips always on top)
    for o in objectsList:
      if isinstance(o, Button) and \
         o.cursorOnObject(mousePos) and \
         not boxSelectionInProgress:
        o.tooltip(screen)

    # Actually draw the stuff to screen
    pygame.display.flip()

    # Save mouse status for next tick
    lmbLastTick, mmbLastTick, rmbLastTick = lmbDown, mmbDown, rmbDown


  # Main loop has been exited; game is ending
  logging.info("Goodbye!")


#_______________________________________________________________________


if __name__ == '__main__':
    main()
