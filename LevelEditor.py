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
# - context menu
# - undo/redo
# - while moving objects: hold CTRL to snap to grid
#
# TODO fixes
# - DONE HelixArc drawing is still wrong
# - observation:   boxselection + mmb/rmb -> boxselection and camera change
#                  at the same time, releasing one cancels boxselection
#   problem:       this isn't user-expected behavior
#   solution idea: while lmb dragging, ignore mmb and rmb; likewise, while
#                  mmb or rmb dragging, ignore lmb (but not mmb or rmb)
#
# TODO else
# - DONE observation:   clicking objects needs pixel-precision
#   problem:       this isn't user-expected behavior, it's uncomfortable,
#                  and impossible to do on touch devices
#   solution idea: 1. copy rendered object sprite (+ padding!)
#                  2. perform Euclidean Distance Transform on copy
#                  3. "clicked" iff (EDT image at click position < threshold)
# - render font objects only once (currently: every frame, and fonts eat CPU)
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
import logging, sys, os
from collections import deque

SCRIPT_PATH = "/opt/mayday"#os.path.dirname(__file__)

WINDOW_SIZE = (800, 600)
ORIGIN = (WINDOW_SIZE[0]//2, WINDOW_SIZE[1]//2)
azimuth_ANGULAR_SPEED = 0.05
ELEVATION_ANGULAR_SPEED = 0.05
ZOOM_IN_SPEED = 1.05
ZOOM_OUT_SPEED = 0.95
MOUSE_azimuth_ANGULAR_SPEED = 0.1
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
# Instead, all pixels within a sphere around the cursor are checked.
# WARNING: Do not set this radius to 0!
CLICK_TOLERANCE_RADIUS  = 5
CLICK_TOLERANCE_OFFSETS = []
for y in range(-CLICK_TOLERANCE_RADIUS,CLICK_TOLERANCE_RADIUS+1):
  for x in range(-CLICK_TOLERANCE_RADIUS,CLICK_TOLERANCE_RADIUS+1):
    if x**2+y**2 > CLICK_TOLERANCE_RADIUS**2+1:
      CLICK_TOLERANCE_OFFSETS.append((x, y))

# A list of all on-screen objects (including buttons!)
objectsList = []
# The currently selected objects
selectedObjects = []
# Holds the strings added by infoMessage(), read by drawHelpDebugInfoMessages()
messageQueue = deque()

# Tells if a click was "doing nothing" (click into empty space)
idleClick = True


tooltip_texts = {"AddStraightButton": "Add a straight path piece",
                 "AppendStraightButton": "Append a straight path piece to a selected path piece"}


#_______________________________________________________________________

class DisplayedObject(object):
  def __init__(self):
    self.surfaceObj = None
    self.rect = None
    self.selected = False
    # Some objects have (unique!) names
    self.name = ""
    self.center = [0,0,0]

  def select(self):
    self.selected = True
  def deselect(self):
    self.selected = False

  def moveTo(self, newPos):
    self.center = newPos[:]

  def moveByPixelOffset(self, relativePixelMotion):
    z = self.center[2]
    ppos = project3dToPixelPosition(self.center)
    ppos[0] += relativePixelMotion[0]
    ppos[1] += relativePixelMotion[1]
    self.moveTo(unprojectPixelTo3dPosition(ppos, ORIGIN, z))

  def render(self):
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
    # return self.rect.collidepoint(mousePos) and \
           # self.surfaceObj.get_at((mousePos[0]-self.rect.topleft[0],
                                   # mousePos[1]-self.rect.topleft[1])) != (0, 0, 0, 0)

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

  def tooltip(self, screen, mousePos=None, text="<<<Button.tooltip().text>>>"):
    """Check cursorOnObject before calling!"""
    if mousePos is None:
      mousePos = pygame.mouse.get_pos()
    tmpTooltipTextObj = pygame.font.SysFont(None, 20).render(text, True, (0, 0, 0), (255, 255, 255))
    tmpTooltipTextObjRect = tmpTooltipTextObj.get_rect()
    tmpTooltipTextObjRect.topright = (mousePos[0]-5, mousePos[1]+5)
    screen.blit(tmpTooltipTextObj, tmpTooltipTextObjRect)


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
    global objectsList
    objectsList.append(Straight((-20,-20,-20),(20,50,20)))
    infoMessage("Straight object added.")

  def tooltip(self, screen, mousePos=None):
    if mousePos is None:
      mousePos = pygame.mouse.get_pos()
    super(AddStraightButton, self).tooltip(screen, mousePos, tooltip_texts["AddStraightButton"])



class AppendStraightButton(Button):
  def __init__(self, name="AppendStraightButton", buttonRect=pygame.Rect(0,0,0,0),
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
    if not selectedObjects:
      infoMessage("must select a single path piece to append (none selected)")
    elif len(selectedObjects) > 1:
      infoMessage("must select a single path piece to append (%d selected)" % len(selectedObjects))
    else:
      infoMessage("I am not doing anything =(")

  def tooltip(self, screen, mousePos=None):
    if mousePos is None:
      mousePos = pygame.mouse.get_pos()
    super(AppendStraightButton, self).tooltip(screen, mousePos, tooltip_texts["AppendStraightButton"])


class Straight(ClickRegisteringObject):
  def __init__(self,
               startPoint3D=[0,0,0], endPoint3D=[0,0,0], color=(0,0,255)):
    super(Straight, self).__init__()
    self.startPoint = startPoint3D
    self.endPoint = endPoint3D
    self.center = [(a+b)/2. for a,b in zip(startPoint3D, endPoint3D)]
    self.color = color
    self.render()

  def render(self):
    """call after viewing direction or zoom change to rerender object"""
    positions = (project3dToPixelPosition(self.startPoint, ORIGIN),
                 project3dToPixelPosition(self.endPoint, ORIGIN))
    min_x = int(min([p[0] for p in positions]))
    max_x = int(max([p[0] for p in positions]))
    min_y = int(min([p[1] for p in positions]))
    max_y = int(max([p[1] for p in positions]))
    start = positions[0]
    end = positions[1]
    linecenter = project3dToPixelPosition(((self.endPoint[0]+self.startPoint[0])/2,
                           (self.endPoint[1]+self.startPoint[1])/2,
                           (self.endPoint[2]+self.startPoint[2])/2), ORIGIN)
    # safely overestimate the needed area (pad to avoid clipping lines)
    tempSurfaceObj = pygame.Surface((max_x-min_x+CLICK_TOLERANCE_RADIUS,
                                     max_y-min_y+CLICK_TOLERANCE_RADIUS))
    tempSurfaceObj = tempSurfaceObj.convert_alpha()
    tempSurfaceObjCenter = (tempSurfaceObj.get_size()[0]//2,
                            tempSurfaceObj.get_size()[1]//2)
    pygame.draw.aaline(tempSurfaceObj, self.color,
                       (positions[0][0]-linecenter[0]+tempSurfaceObjCenter[0],
                        positions[0][1]-linecenter[1]+tempSurfaceObjCenter[1]),
                       (positions[1][0]-linecenter[0]+tempSurfaceObjCenter[0],
                        positions[1][1]-linecenter[1]+tempSurfaceObjCenter[1]))
    # repair the alpha values (transparency) at antialiasing border
    pixels = pygame.PixelArray(tempSurfaceObj)
    pixels.replace(pygame.Color(0, 0, 0, 255), pygame.Color(0, 0, 0, 0))
    del pixels
    tempSurfaceObjRect = tempSurfaceObj.get_rect()
    tempSurfaceObjRect.center = linecenter
    self.surfaceObj = tempSurfaceObj
    self.rect = tempSurfaceObjRect



class HelixArc(ClickRegisteringObject):
  def __init__(self,
               startHeight=-40., endHeight=40.,
               startAngle=0., endAngle=720.,
               radius=50., center=[0,0,0],
               rightHanded=True, color=(0,0,255)):
    super(HelixArc, self).__init__()
    self.center = center[:]
    self.centershift = [0,0]
    self.color = color
    steps = endAngle - startAngle
    heightstep = (endHeight-startHeight)/steps
    stepsize = (endAngle-startAngle)/steps
    height, angle = startHeight, startAngle
    self.points3d = []
    self.points3dHD = []
    step = 0
    while step < steps:
      a = angle if rightHanded else (360.-angle)
      x = cos(a*(pi/180.))*radius + center[0]
      y = sin(a*(pi/180.))*radius + center[1]
      z = height + center[2]
      self.points3dHD.append((x,y,z))
      if step % 10 == 0 or step == 999:
        self.points3d.append((x,y,z))
      angle += stepsize
      height += heightstep
      step += 1
    self.render()

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
      pixels.append((px,py))
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

    # Draw sample points, using Wu-style antialiasing
    # NOTE that AA is performed using only the alpha channel!
    for p in pixels:
      xint, xfrac = divmod(p[0], 1)
      yint, yfrac = divmod(p[1], 1)

      if 0 <= int(xint)-int(minx)+pad < WINDOW_SIZE[0] and \
         0 <= int(yint)-int(miny)+pad < WINDOW_SIZE[1]:
        c = sf.get_at((int(xint)-int(minx)+pad,int(yint)-int(miny)+pad))
        c.r, c.g, c.b = self.color
        c.a=max(c.a,int(255*(1.-xfrac)*(1.-yfrac)))
        sf.set_at((int(xint)-int(minx)+pad,int(yint)-int(miny)+pad),c)

      if 0 <= int(xint)+1-int(minx)+pad < WINDOW_SIZE[0] and \
         0 <= int(yint)-int(miny)+pad < WINDOW_SIZE[1]:
        c = sf.get_at((int(xint)+1-int(minx)+pad,int(yint)-int(miny)+pad))
        c.r, c.g, c.b = self.color
        c.a=max(c.a,int(255*(xfrac)*(1.-yfrac)))
        sf.set_at((int(xint)+1-int(minx)+pad,int(yint)-int(miny)+pad),c)

      if 0 <= int(xint)-int(minx)+pad < WINDOW_SIZE[0] and \
         0 <= int(yint)+1-int(miny)+pad < WINDOW_SIZE[1]:
        c = sf.get_at((int(xint)-int(minx)+pad,int(yint)+1-int(miny)+pad))
        c.r, c.g, c.b = self.color
        c.a=max(c.a,int(255*(1.-xfrac)*(yfrac)))
        sf.set_at((int(xint)-int(minx)+pad,int(yint)+1-int(miny)+pad),c)

      if 0 <= int(xint)+1-int(minx)+pad < WINDOW_SIZE[0] and \
         0 <= int(yint)+1-int(miny)+pad < WINDOW_SIZE[1]:
        c = sf.get_at((int(xint)+1-int(minx)+pad,int(yint)+1-int(miny)+pad))
        c.r, c.g, c.b = self.color
        c.a=max(c.a,int(255*(xfrac)*(yfrac)))
        sf.set_at((int(xint)+1-int(minx)+pad,int(yint)+1-int(miny)+pad),c)

    r = sf.get_rect()
    r.center = [ORIGIN[0]+self.centershift[0], ORIGIN[1]+self.centershift[1]]
    self.surfaceObj = sf
    self.rect = r

  def draw(self, screen):
    """
    The HelixArc needs special treatment, as its boundingbox depends heavily
    on the viewing direction.
    """
    ppos = project3dToPixelPosition(self.center)
    self.rect.center = [ppos[0]+self.centershift[0],
                        ppos[1]+self.centershift[1]]
    screen.blit(self.surfaceObj, self.rect)


#_______________________________________________________________________


def getObjectByName(name):
  "Identify objects having unique names"
  global objectsList
  result = [o for o in objectsList if o.name==name]
  if not result:
    raise IndexError('Objectslist contains no object named "%s"!' % name)
  elif len(result) > 1:
    raise IndexError('Objectslist contains multiple objects named "%s"!' % name)
  return result[0]

def getObjectsByClass(cls):
  "Identify objects by their class"
  global objectsList
  result = [o for o in objectsList if isinstance(o, cls)]
  if not result:
    raise IndexError('Objectslist contains no object of class "%s"!' % cls.__name__)
  return result

def compute_projection_parameters(newazimuth, newelevation, newzoom):
  "Changes the camera perspective"
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
  result = [c[0] * right[0] + c[1] * front[0] + c[2] * up[0],
            c[0] * right[1] + c[1] * front[1] + c[2] * up[1]]
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
  point3d = (x, y, z)
  return point3d


def drawHelpLines(pos3D, screen):
  """Draw 3D orientation help lines"""
  positions = (project3dToPixelPosition((0, 0, 0)),
               project3dToPixelPosition((pos3D[0], 0, 0)),
               project3dToPixelPosition((pos3D[0], pos3D[1], 0)),
               project3dToPixelPosition(pos3D))
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
    line_anchors.append((positions[i+1][0]-start[0]+tempSurfaceObjCenter[0],
                         positions[i+1][1]-start[1]+tempSurfaceObjCenter[1]))
    pygame.draw.aaline(tempSurfaceObj, (0,0,127),
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
                       project3dToPixelPosition(((i-10)*50,-500, 0)),
                       project3dToPixelPosition(((i-10)*50, 500, 0)))
    pygame.draw.aaline(BGSurfaceObj, (255,255,255),
                       project3dToPixelPosition((-500, (i-10)*50, 0)),
                       project3dToPixelPosition(( 500, (i-10)*50, 0)))
  return BGSurfaceObj




def makeGUIButtons():
  """Initialize GUI buttons"""
  buttons = []
  to_make = ((AddStraightButton, "addStraightButton",
                (WINDOW_SIZE[0], 0)),
             (AppendStraightButton, "appendStraightButton",
                (WINDOW_SIZE[0]-50, 0)))

  for buttonClass, name, (x,y) in to_make:
    newButton = buttonClass(name)
    rect = newButton.surfaceObj.get_rect()
    rect.topright = (x,y)
    newButton.setRectangle(rect)
    buttons.append(newButton)

  global objectsList
  objectsList.extend(buttons)
  getObjectByName("appendStraightButton").disable()



def infoMessage(msg):
  """Append a message to the queue and keep the queue at a max length"""
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
  global selectedObjects
  for o in selectedObjects:
    if not o.inRect(rect):
      deselectObjects(o)



def drawHelpDebugInfoMessages(screen):
  """draw helpful texts and print the info message queue"""
  global selectedObjects
  for so in selectedObjects:
    pos = so.center
    ppos = project3dToPixelPosition(pos)
    # render info text at (and about) position (3D -> pixels)
    text = '(%.1f, %.1f, %.1f) -> (%d, %d)'%(pos[0], pos[1], pos[2],
                                             ppos[0], ppos[1])
    textObj = pygame.font.SysFont(None, 18).render(text, True, (0, 0, 0))
    textRect = textObj.get_rect()
    textRect.topleft = (ppos[0]+10, ppos[1])
    screen.blit(textObj, textRect)
  # render info text about azimuth and elevation angles
  lines = ["azimuth angle = %.2f RAD (ca. %d DEG)" % (azimuth, azimuth*180./pi),
           "Elevation angle = %.2f RAD (ca. %d DEG)" % (elevation, elevation*180./pi),
           "Zoom factor = %.2f" % zoom]
  for i in range(3):
    textObj = pygame.font.SysFont(None, 18).render(lines[i], True, (0, 0, 0))
    textRect = textObj.get_rect()
    textRect.topleft = (0, (i+1)*15)
    screen.blit(textObj, textRect)
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
    screen.blit(textObj, textRect)
  for i, m in enumerate(messageQueue):
    textObj = pygame.font.SysFont(None, 18).render(messageQueue[i], True, (0, 0, 0))
    textRect = textObj.get_rect()
    textRect.topright = (WINDOW_SIZE[0]-5, WINDOW_SIZE[1]-(i+1)*15)
    screen.blit(textObj, textRect)


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

  # initialize pygame
  pygame.init()
  screen = pygame.display.set_mode(WINDOW_SIZE)

  # Set window icon
  # Image credit: http://chidioparareports.blogspot.de/2012/06/special-report-nigerian-airlines-and.html
  icon = pygame.image.load('{}/img/icon.png'.format(SCRIPT_PATH))
  pygame.display.set_icon(icon)

  # set window title
  pygame.display.set_caption("Mayday Level Editor / Camera Demo")

  # set mouse visible
  pygame.mouse.set_visible(1)

  # create clock object used to limit the framerate
  clock = pygame.time.Clock()
  # repeat keypresses as long as the are held down (=resending events?)
  pygame.key.set_repeat(1, 30)

  # render the initial background ("floor" grid)
  BGSurfaceObj = render_background()

  # create GUI buttons
  makeGUIButtons()

  boxSelectionInProgress = False
  boxStartPoint = (0, 0)

  # How far the mouse has travelled with a button down, used to distinguish
  # between "click" and "drag" actions
  dragManhattanDistance = 0
  # Prevents "slipping" off GUI buttons into dragging mode
  dragStartedOnGUI = False
  # Mouse status saved from previous timetick
  lmbLastTick = mmbLastTick = rmbLastTick = False
  # Used for moving objects
  dragStartedOnSelectedObject = False

  # Print info and debugging text?
  printDebug = False

  # Occasionally render HelixArcs in high quality
  framesWithoutRerendering = 0

  ### DEBUG
  objectsList.append(HelixArc())

  # MAIN LOOP
  running = True
  while running:
    # Limit to 30 fps
    clock.tick(30)

    # pygame.mouse.get_pressed() only works after depleting the event queue
    thisTickEvents = pygame.event.get()

    # Check current status of mouse buttons (not events)
    lmbDown, mmbDown, rmbDown = pygame.mouse.get_pressed()

    # Get relative mouse movement since the last timetick
    mouseRelativeMotionThisTick = pygame.mouse.get_rel()

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
       not boxSelectionInProgress and \
       not dragStartedOnGUI and \
       not dragStartedOnSelectedObject:
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
      elif event.type == pygame.KEYDOWN:
        if event.key == pygame.K_ESCAPE:
          logging.debug("Quitting (ESC key)")
          running = False
      # A mouse button was clicked
      elif event.type == pygame.MOUSEBUTTONDOWN:
        # Buttons 1-3 are LMB, MMB, RMB
        if event.button < 4:
          idleClick = True
          # LMB click activates GUI elements, selects objects
          if lmbDown:
            GUIwasClicked = False
            for o in objectsList:
              if isinstance(o, Button) and o.cursorOnObject():
                GUIwasClicked = True
                dragStartedOnGUI = True
                infoMessage("dragStartedOnGUI")
                o.activate()
                o.clickAction()
            if not GUIwasClicked:
              for so in selectedObjects:
                if so.cursorOnObject():
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
        if lmbLastTick and not boxSelectionInProgress:
          deselectObjects()
        # Only "click"-select objects (box selection is done later)
        if not boxSelectionInProgress:
          for o in objectsList:
            if o.cursorOnObject() and not isinstance(o, Button):
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
        boxSelectionInProgress = False
        dragStartedOnGUI = False
        dragStartedOnSelectedObject = False

    # Check current status of keyboard keys
    pressedKeys = pygame.key.get_pressed()

    if pressedKeys[pygame.K_h] and not pressedKeysLastTick[pygame.K_h]:
      printDebug = not printDebug
    # Change camera settings using keyboard
    if pressedKeys[pygame.K_a] and not \
       pressedKeys[pygame.K_LCTRL] or pressedKeys[pygame.K_RCTRL]:
      compute_projection_parameters(azimuth-azimuth_ANGULAR_SPEED, elevation, zoom)
      rerender = True
    if pressedKeys[pygame.K_d]:
      compute_projection_parameters(azimuth+azimuth_ANGULAR_SPEED, elevation, zoom)
      rerender = True
    if pressedKeys[pygame.K_w]:
      compute_projection_parameters(azimuth, elevation+ELEVATION_ANGULAR_SPEED, zoom)
      rerender = True
    if pressedKeys[pygame.K_s]:
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
          compute_projection_parameters(azimuth-azimuth_ANGULAR_SPEED*
                                                 mouseRelativeMotionThisTick[0]*
                                                 MOUSE_azimuth_ANGULAR_SPEED,
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

    ## Special keyboard commands
    # Ctrl+A: Select all objects
    if pressedKeys[pygame.K_a] and not pressedKeysLastTick[pygame.K_a] and \
       pressedKeys[pygame.K_LCTRL] or pressedKeys[pygame.K_RCTRL]:
      infoMessage("Select all")
      for o in objectsList:
        if not isinstance(o, Button):
          selectObjects(o)

    # Move selected objects per keyboard
    for so in selectedObjects:
      if pressedKeys[pygame.K_UP]:
        so.center[1] += 10
      if pressedKeys[pygame.K_DOWN]:
        so.center[1] -= 10
      if pressedKeys[pygame.K_LEFT]:
        so.center[0] -= 10
      if pressedKeys[pygame.K_RIGHT]:
        so.center[0] += 10
      if pressedKeys[pygame.K_PAGEUP]:
        so.center[2] += 10
      if pressedKeys[pygame.K_PAGEDOWN]:
        so.center[2] -= 10

    # Move selected objects per mouse
    if dragManhattanDistance > DRAGGING_DISTANCE_THRESHOLD and \
       dragStartedOnSelectedObject:
      # Motion along z-axis
      if pressedKeys[pygame.K_RSHIFT] or pressedKeys[pygame.K_LSHIFT]:
        for so in selectedObjects:
          so.moveTo([so.center[0],
                     so.center[1],
                     so.center[2]-mouseRelativeMotionThisTick[1]])
      # Motion along z=0 plane
      else:
        for so in selectedObjects:
          so.moveByPixelOffset(mouseRelativeMotionThisTick)

    # If the camera has changed, the background graphic has to be re-rendered
    if rerender:
      framesWithoutRerendering = 0
      BGSurfaceObj = render_background()
      for o in objectsList:
        o.render()
    else:
      framesWithoutRerendering += 1

    # Render HelixArcs in good quality if the scene is stationary
    if framesWithoutRerendering == 3:
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

    # Print helpful information and debugging messages (CPU intensive!)
    text = 'Press H to toggle debug information.'
    textObj = pygame.font.SysFont(None, 18).render(text, True, (0, 0, 0))
    textRect = textObj.get_rect()
    textRect.topleft = (0,0)
    screen.blit(textObj, textRect)
    if printDebug:
      drawHelpDebugInfoMessages(screen)

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
      selectionBoxRect.center = (.5*(boxStartPoint[0]+boxEndPoint[0]),
                                 .5*(boxStartPoint[1]+boxEndPoint[1]))
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
    if not selectedObjects or \
       len(selectedObjects) != 1 or \
       len([o for o in selectedObjects if isinstance(o, Straight)]) != 1:
      getObjectByName('appendStraightButton').disable()
    else:
      getObjectByName('appendStraightButton').enable()

    # Draw GUI buttons
    for o in objectsList:
      if isinstance(o, Button):
        if o.cursorOnObject() and \
           not dragManhattanDistance > DRAGGING_DISTANCE_THRESHOLD :
          o.highlight()
          o.draw(screen)
          o.dehighlight()
        else:
          o.draw(screen)

    # Draw GUI tooltips (after drawing all buttons -> tooltips always on top)
    for o in objectsList:
      if isinstance(o, Button) and \
         o.cursorOnObject() and \
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
