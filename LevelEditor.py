#!/usr/bin/env python
# -*- coding: UTF-8 -*-

# Copyright 2013
# Author: Nikolaus Mayer


########################################################################
# TODO
# - mouse camera DONE
# - clickable game objects / how precise? DONE
# - z-ordering (treap?)
# - adding DONE / moving objects
# - autojoining objects at ends to form a path
# - context menu
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

SCRIPT_PATH = os.path.dirname(__file__)

WINDOW_SIZE = (800, 600)
ORIGIN = (WINDOW_SIZE[0]//2, WINDOW_SIZE[1]//2)
ROTATION_ANGULAR_SPEED = 0.05
ELEVATION_ANGULAR_SPEED = 0.05
ZOOM_IN_SPEED = 1.05
ZOOM_OUT_SPEED = 0.95
MOUSE_ROTATION_ANGULAR_SPEED = 0.1
MOUSE_ELEVATION_ANGULAR_SPEED = 0.1
MOUSE_ZOOM_IN_SPEED = 0.1
MOUSE_ZOOM_OUT_SPEED = 0.1

# Don't have to hold the mouse perfectly still for "clicks" (vs dragging)
DRAGGING_DISTANCE_THRESHOLD = 5

rotation = -45.*(pi/180.)
elevation = -66.*(pi/180.)
right = [cos(rotation), sin(rotation) * cos(elevation)]
front = [sin(rotation), -cos(rotation) * cos(elevation)]
up = [0, sin(elevation)]
zoom = 1.

objectsList = []
selectedObjects = []
messageQueue = deque()

# Tells if a click was "doing nothing" (click into empty space)
idleClick = True


tooltip_texts = {"AddStraightButton": "Add a straight path piece",
                 "AppendStraightButton": "Append a straight path piece to a selected path piece"}


#_______________________________________________________________________

class displayedObject(object):
  def __init__(self):
    self.surfaceObj = None
    self.rect = None
    self.selected = False
    # Some objects have (unique!) names
    self.name = ""

  def select(self):
    self.selected = True
  def deselect(self):
    self.selected = False

  def render(self):
    return None

  def draw(self, screen):
    """
    Draw to screen
    IMPORTANT: Call self.render() before if the object's appearance depends
               on the camera pose!
    """
    screen.blit(self.surfaceObj, self.rect)


class clickRegisteringObject(displayedObject):
  def __init__(self):
    super(clickRegisteringObject, self).__init__()

  def cursorOnObject(self, mousePos=None):
    if mousePos is None:
      mousePos = pygame.mouse.get_pos()
    return self.rect.collidepoint(mousePos) and \
           self.surfaceObj.get_at((mousePos[0]-self.rect.topleft[0],
                                   mousePos[1]-self.rect.topleft[1])) != (0, 0, 0, 0)

  def inRect(self, rect):
    return rect.collidepoint(self.rect.center)



class Button(clickRegisteringObject):
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

  def tooltip(self, screen, mousePos=None, text="<<<self.tooltip.text>>>"):
    """check cursorOnObject before calling!"""
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


class Straight(clickRegisteringObject):
  def __init__(self,
               startPoint3D=(0,0,0), endPoint3D=(0,0,0), color=(0,0,255)):
    super(Straight, self).__init__()
    self.startPoint = startPoint3D
    self.endPoint = endPoint3D
    self.color = color
    self.render()

  def render(self):
    """call after viewing direction or zoom change to rerender object"""
    positions = (pixelpos(self.startPoint, ORIGIN),
                 pixelpos(self.endPoint, ORIGIN))
    min_x = int(min([p[0] for p in positions]))
    max_x = int(max([p[0] for p in positions]))
    min_y = int(min([p[1] for p in positions]))
    max_y = int(max([p[1] for p in positions]))
    start = positions[0]
    end = positions[1]
    linecenter = pixelpos(((self.endPoint[0]+self.startPoint[0])/2,
                           (self.endPoint[1]+self.startPoint[1])/2,
                           (self.endPoint[2]+self.startPoint[2])/2), ORIGIN)
    # safely overestimate the needed area (pad to avoid clipping lines)
    tempSurfaceObj = pygame.Surface((max_x-min_x+5, max_y-min_y+5))
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



class HelixArc(clickRegisteringObject):
  def __init__(self,
               startHeight=-40., endHeight=40.,
               startAngle=0., endAngle=720.,
               radius=50., centerpoint=(0,0,0),
               rightHanded=True, color=(0,0,255)):
    super(HelixArc, self).__init__()
    self.color = color
    steps = 1000
    heightstep = (endHeight-startHeight)/steps
    stepsize = (endAngle-startAngle)/steps
    height, angle = startHeight, startAngle
    self.points3d = []
    self.points3dHD = []
    step = 0
    while angle < endAngle:
      a = angle if rightHanded else (360.-angle)
      x = cos(a*(pi/180.))*radius + centerpoint[0]
      y = sin(a*(pi/180.))*radius + centerpoint[1]
      z = height + centerpoint[2]
      self.points3dHD.append((x,y,z))
      if step % 10 == 0:
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
      px, py = pixelpos(p, (0,0))
      pixels.append((px,py))
      minx=min(minx,px)
      miny=min(miny,py)
      maxx=max(maxx,px)
      maxy=max(maxy,py)
    centershift = (maxx+minx)/2,(maxy+miny)/2
    sf = pygame.Surface((maxx-minx+4,maxy-miny+4))
    sf = sf.convert_alpha()
    sf.fill((0,0,0,0))
    sfsize=sf.get_size()

    # Draw sample points, using Wu-style antialiasing
    # NOTE that AA is performed using only the alpha channel!
    for p in pixels:
      xint, xfrac = divmod(p[0], 1)
      yint, yfrac = divmod(p[1], 1)

      if 0 <= int(xint)-int(minx)+2 < WINDOW_SIZE[0] and \
         0 <= int(yint)-int(miny)+2 < WINDOW_SIZE[1]:
        c = sf.get_at((int(xint)-int(minx)+2,int(yint)-int(miny)+2))
        c.r, c.g, c.b = self.color
        c.a=max(c.a,int(255*(1.-xfrac)*(1.-yfrac)))
        sf.set_at((int(xint)-int(minx)+2,int(yint)-int(miny)+2),c)

      if 0 <= int(xint)+1-int(minx)+2 < WINDOW_SIZE[0] and \
         0 <= int(yint)-int(miny)+2 < WINDOW_SIZE[1]:
        c = sf.get_at((int(xint)+1-int(minx)+2,int(yint)-int(miny)+2))
        c.r, c.g, c.b = self.color
        c.a=max(c.a,int(255*(xfrac)*(1.-yfrac)))
        sf.set_at((int(xint)+1-int(minx)+2,int(yint)-int(miny)+2),c)

      if 0 <= int(xint)-int(minx)+2 < WINDOW_SIZE[0] and \
         0 <= int(yint)+1-int(miny)+2 < WINDOW_SIZE[1]:
        c = sf.get_at((int(xint)-int(minx)+2,int(yint)+1-int(miny)+2))
        c.r, c.g, c.b = self.color
        c.a=max(c.a,int(255*(1.-xfrac)*(yfrac)))
        sf.set_at((int(xint)-int(minx)+2,int(yint)+1-int(miny)+2),c)

      if 0 <= int(xint)+1-int(minx)+2 < WINDOW_SIZE[0] and \
         0 <= int(yint)+1-int(miny)+2 < WINDOW_SIZE[1]:
        c = sf.get_at((int(xint)+1-int(minx)+2,int(yint)+1-int(miny)+2))
        c.r, c.g, c.b = self.color
        c.a=max(c.a,int(255*(xfrac)*(yfrac)))
        sf.set_at((int(xint)+1-int(minx)+2,int(yint)+1-int(miny)+2),c)

    r = sf.get_rect()
    r.center=(ORIGIN[0]+centershift[0], ORIGIN[1]+centershift[1])
    self.surfaceObj = sf
    self.rect = r


#_______________________________________________________________________


def getObjectByName(name):
  "identify objects having unique names"
  global objectsList
  result = [o for o in objectsList if o.name==name]
  if not result:
    raise IndexError('Objectslist contains no object named "%s"!' % name)
  elif len(result) > 1:
    raise IndexError('Objectslist contains multiple objects named "%s"!' % name)
  else:
    return result[0]


def compute_projection_parameters(newrotation, newelevation, newzoom):
  "changes the camera perspective"
  global rotation, elevation, right, front, up, zoom
  rotation = newrotation
  while rotation < 0.: rotation += 2*pi
  while rotation > 2*pi: rotation -= 2*pi
  elevation = min(0., max(-pi, newelevation))
  right = [cos(rotation), sin(rotation) * cos(elevation)]
  front = [sin(rotation), -cos(rotation) * cos(elevation)]
  up = [0, sin(elevation)]
  zoom = newzoom

def pixelpos(c, ORIGIN):
  "computes the 2D pixel screen coordinate for a 3D coordinate"
  # isometric projection
  result = [c[0] * right[0] + c[1] * front[0] + c[2] * up[0],
            c[0] * right[1] + c[1] * front[1] + c[2] * up[1]]
  result[0] *= zoom
  result[1] *= zoom
  # compensate for pixel shift (window center is world center)
  result[0] += ORIGIN[0]
  result[1] += ORIGIN[1]
  return result


def drawHelpLines(pos3D, screen):
  "draw 3D orientation help lines"
  positions = (pixelpos((0, 0, 0), ORIGIN),
               pixelpos((pos3D[0], 0, 0), ORIGIN),
               pixelpos((pos3D[0], pos3D[1], 0), ORIGIN),
               pixelpos(pos3D, ORIGIN))
  min_x = int(min([p[0] for p in positions]))
  max_x = int(max([p[0] for p in positions]))
  min_y = int(min([p[1] for p in positions]))
  max_y = int(max([p[1] for p in positions]))
  start = positions[0]
  end = positions[-1]
  # safely overestimate the needed area (pad to avoid clipping lines)
  tempSurfaceObj = pygame.Surface((2*max([abs(max_x-start[0]),
                                          abs(min_x-start[0])])+5,
                                   2*max([abs(max_y-start[1]),
                                          abs(min_y-start[1])])+5))
  tempSurfaceObj = tempSurfaceObj.convert_alpha()
  tempSurfaceObjCenter = (tempSurfaceObj.get_size()[0]//2,
                          tempSurfaceObj.get_size()[1]//2)
  line_anchors = [tempSurfaceObjCenter]
  # draw a path from the origin to the cursor along the 3 dimensions
  for i in range(3):
    line_anchors.append((positions[i+1][0]-start[0]+tempSurfaceObjCenter[0],
                         positions[i+1][1]-start[1]+tempSurfaceObjCenter[1]))
    pygame.draw.aaline(tempSurfaceObj, (0,0,127),
                       line_anchors[i], line_anchors[i+1])
  # repair the alpha values (transparency) at antialiasing border
  pixels = pygame.PixelArray(tempSurfaceObj)
  pixels.replace(pygame.Color(0, 0, 0, 255), pygame.Color(0, 0, 0, 0))
  del pixels
  # draw
  tempSurfaceObjRect = tempSurfaceObj.get_rect()
  tempSurfaceObjRect.center = ORIGIN
  screen.blit(tempSurfaceObj, tempSurfaceObjRect)


def render_background(screen):
  "rerender the 'ground' (z=0 plane) grid"
  # create and fill background
  BGSurfaceObj = pygame.Surface(WINDOW_SIZE)
  BGSurfaceObj.fill((200,200,255))
  # render grid lines
  for i in range(21):
    pygame.draw.aaline(BGSurfaceObj, (255,255,255),
                       pixelpos(((i-10)*50,-500, 0), ORIGIN),
                       pixelpos(((i-10)*50, 500, 0), ORIGIN))
    pygame.draw.aaline(BGSurfaceObj, (255,255,255),
                       pixelpos((-500, (i-10)*50, 0), ORIGIN),
                       pixelpos(( 500, (i-10)*50, 0), ORIGIN))
  return BGSurfaceObj




def makeGUIButtons():
  """initialize GUI buttons, returns a list of BUTTONs"""
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
  """append a message to the queue and keep the queue at a max length"""
  messageQueue.append(msg)
  if len(messageQueue) > 8:
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



def drawHelpDebugInfoMessages(screen, cursor_position, cursorPixelPos):
  """draw helpful texts and print the info message queue"""
    # render info text at (and about) cursor position (3D -> pixels)
  text = '(%.1f, %.1f, %.1f) -> (%d, %d)'%(cursor_position[0], cursor_position[1], cursor_position[2],
                                           cursorPixelPos[0], cursorPixelPos[1])
  textObj = pygame.font.SysFont(None, 18).render(text, True, (0, 0, 0))
  textRect = textObj.get_rect()
  textRect.topleft = (cursorPixelPos[0]+10, cursorPixelPos[1])
  screen.blit(textObj, textRect)
  # render info text about rotation and elevation angles
  lines = ["Rotation angle = %.2f RAD (ca. %d DEG)" % (rotation, rotation*180./pi),
           "Elevation angle = %.2f RAD (ca. %d DEG)" % (elevation, elevation*180./pi),
           "Zoom factor = %.2f" % zoom]
  for i in range(3):
    textObj = pygame.font.SysFont(None, 18).render(lines[i], True, (0, 0, 0))
    textRect = textObj.get_rect()
    textRect.topleft = (0, (i+1)*15)
    screen.blit(textObj, textRect)
  lines = ["Use WASD or MIDDLE MOUSE BUTTON to rotate the camera (isometric projection).",
           "Move the cursor with the ARROW KEYS and PAGE-UP/DOWN.",
           "Zoom in and out using the + (plus) and - (minus) keys or RIGHT MOUSE BUTTON.",
           "Press HOME to reset the camera."]
  for i in range(4):
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

  # set window title
  pygame.display.set_caption("Mayday Level Editor / Camera Demo")

  # set mouse visible
  pygame.mouse.set_visible(1)

  # create clock object used to limit the framerate
  clock = pygame.time.Clock()
  # repeat keypresses as long as the are held down (=resending events?)
  pygame.key.set_repeat(1, 30)

  # render the initial background ("floor" grid)
  BGSurfaceObj = render_background(screen)

  # create a small cursor
  cursor_position = [0, 0, 0]
  CursorSurfaceObj = pygame.Surface((1, 1))
  CursorSurfaceObj.fill((0, 0, 0))

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
    mouseRelX, mouseRelY = pygame.mouse.get_rel()

    # Update dragManhattanDistance if the button status has not changed
    if (lmbDown and lmbLastTick) or \
       (mmbDown and mmbLastTick) or \
       (rmbDown and rmbLastTick):
      dragManhattanDistance += abs(mouseRelX)+abs(mouseRelY)
    elif lmbDown or mmbDown or rmbDown:
      dragManhattanDistance = 0

    if lmbDown and \
       dragManhattanDistance > DRAGGING_DISTANCE_THRESHOLD and \
       not boxSelectionInProgress and \
       not dragStartedOnGUI:
      deselectObjects()
      boxSelectionInProgress = True
      boxStartPoint = pygame.mouse.get_pos()

    if dragManhattanDistance > DRAGGING_DISTANCE_THRESHOLD:
      idleClick = False

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
        idleClick = True
        # LMB click activates GUI elements, selects objects
        if lmbDown:
          GUIwasClicked = False
          for o in objectsList:
            if isinstance(o, Button) and o.cursorOnObject():
              GUIwasClicked = True
              dragStartedOnGUI = True
              o.activate()
              o.clickAction()
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

    # Check current status of keyboard keys
    pressedKeys = pygame.key.get_pressed()
    rerender = False

    if pressedKeys[pygame.K_h] and not pressedKeysLastTick[pygame.K_h]:
      printDebug = not printDebug

    # Move cursor
    if pressedKeys[pygame.K_UP]:
      cursor_position[1] += 10
    if pressedKeys[pygame.K_DOWN]:
      cursor_position[1] -= 10
    if pressedKeys[pygame.K_LEFT]:
      cursor_position[0] -= 10
    if pressedKeys[pygame.K_RIGHT]:
      cursor_position[0] += 10
    if pressedKeys[pygame.K_PAGEUP]:
      cursor_position[2] += 10
    if pressedKeys[pygame.K_PAGEDOWN]:
      cursor_position[2] -= 10

    # Change camera settings using keyboard
    if pressedKeys[pygame.K_a]:
      compute_projection_parameters(rotation-ROTATION_ANGULAR_SPEED, elevation, zoom)
      rerender = True
    if pressedKeys[pygame.K_d]:
      compute_projection_parameters(rotation+ROTATION_ANGULAR_SPEED, elevation, zoom)
      rerender = True
    if pressedKeys[pygame.K_w]:
      compute_projection_parameters(rotation, elevation+ELEVATION_ANGULAR_SPEED, zoom)
      rerender = True
    if pressedKeys[pygame.K_s]:
      compute_projection_parameters(rotation, elevation-ELEVATION_ANGULAR_SPEED, zoom)
      rerender = True
    if pressedKeys[pygame.K_HOME]:
      compute_projection_parameters(-45*(pi/180.), -66*(pi/180.), 1.0)
      rerender = True
    if pressedKeys[pygame.K_MINUS]:
      compute_projection_parameters(rotation, elevation, zoom*ZOOM_OUT_SPEED)
      rerender = True
    if pressedKeys[pygame.K_PLUS]:
      compute_projection_parameters(rotation, elevation, zoom*ZOOM_IN_SPEED)
      rerender = True

    pressedKeysLastTick = pressedKeys

    ## Change camera settings using mouse
    # Rotation and Elevation angles
    if dragManhattanDistance > DRAGGING_DISTANCE_THRESHOLD:
      if mmbDown:
        if mouseRelX != 0 or mouseRelY != 0:
          compute_projection_parameters(rotation-ROTATION_ANGULAR_SPEED*
                                                 mouseRelX*
                                                 MOUSE_ROTATION_ANGULAR_SPEED,
                                        elevation+ELEVATION_ANGULAR_SPEED*
                                                  mouseRelY*
                                                  MOUSE_ELEVATION_ANGULAR_SPEED,
                                        zoom)
          rerender = True
      # Zoom factor
      if rmbDown:
        if mouseRelY < 0:
          compute_projection_parameters(rotation,
                                        elevation,
                                        zoom*ZOOM_IN_SPEED**
                                          (-mouseRelY*MOUSE_ZOOM_IN_SPEED))
          rerender = True
        if mouseRelY > 0:
          compute_projection_parameters(rotation,
                                        elevation,
                                        zoom*ZOOM_OUT_SPEED**
                                          (mouseRelY*MOUSE_ZOOM_OUT_SPEED))
          rerender = True

    # If the camera has changed, the background graphic has to be re-rendered
    if rerender:
      framesWithoutRerendering = 0
      BGSurfaceObj = render_background(screen)
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


    # Draw cursor
    screen.blit(BGSurfaceObj, (0, 0))
    cursorPixelPos = pixelpos(cursor_position, ORIGIN)
    screen.blit(CursorSurfaceObj, cursorPixelPos)

    # Print helpful information and debugging messages (CPU intensive!)
    text = 'Press H to toggle debug information.'
    textObj = pygame.font.SysFont(None, 18).render(text, True, (0, 0, 0))
    textRect = textObj.get_rect()
    textRect.topleft = (0,0)
    screen.blit(textObj, textRect)
    if printDebug:
      drawHelpDebugInfoMessages(screen, cursor_position, cursorPixelPos)


    # Draw lines to visualize the cursor's position in 3D space
    # TODO we don't need a cursor, use this to mark a single selected object?
    drawHelpLines(cursor_position, screen)

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
