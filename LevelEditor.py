#!/usr/bin/env python
# -*- coding: UTF-8 -*-

# Copyright 2013
# Author: Nikolaus Mayer


########################################################################
# TODO
# - mouse camera ?
# - clickable game objects / how precise?
# - z-ordering
# - adding / moving objects
# - autojoining objects at ends to form a path
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

rotation = -45*(pi/180.)
elevation = -66*(pi/180.)
right = [cos(rotation), sin(rotation) * cos(elevation)]
front = [sin(rotation), -cos(rotation) * cos(elevation)]
up = [0, sin(elevation)]
zoom = 1.

objectsList = []
selectedObjects = []
messageQueue = deque()


class displayedObject(object):
  def __init__(self):
    self.surfaceObj = None
    self.rect = None


class clickRegisteringObject(displayedObject):
  def __init__(self):
    super(clickRegisteringObject, self).__init__()

  def checkClicked(self):
    mouse = pygame.mouse.get_pos()
    return self.rect.collidepoint(mouse) and \
           self.surfaceObj.get_at((mouse[0]-self.rect.topleft[0],
                                   mouse[1]-self.rect.topleft[1])) != (0, 0, 0, 0)

  def inRect(self, rect):
    return rect.collidepoint(self.rect.center)



class Button(clickRegisteringObject):
  def __init__(self, name="", buttonRect=pygame.Rect(0,0,0,0),
               buttonSurfaceObj=pygame.Surface((0,0)),
               buttonClickedSurfaceObj=pygame.Surface((0,0))):
    self.name = name
    self.surfaceObj = buttonSurfaceObj
    self.clickedSurfaceObj = buttonClickedSurfaceObj
    self.rect = buttonRect
    self.active = False

  def clickAction(self):
    pass

  def setRectangle(self, newRectangle):
    self.rect = newRectangle

  def activate(self):
    self.active = True

  def deactivate(self):
    self.active = False

  def draw(self, screen):
    if self.active:
      screen.blit(self.clickedSurfaceObj, self.rect)
    else:
      screen.blit(self.surfaceObj, self.rect)


class AddStraightButton(Button):
  def __init__(self, name="AddStraightButton", buttonRect=pygame.Rect(0,0,0,0),
               buttonSurfaceObj=pygame.Surface((0,0)),
               buttonClickedSurfaceObj=pygame.Surface((0,0))):
    img = pygame.image.load('{}/img/straight.png'.format(SCRIPT_PATH))
    clickedImg = pygame.image.load('{}/img/straightClicked.png'.format(SCRIPT_PATH))
    super(AddStraightButton, self).__init__(name, buttonRect, img, clickedImg)

  def clickAction(self):
    global objectsList
    objectsList.append(Straight((-20,-20,-20),(20,50,20)))


class Straight(clickRegisteringObject):
  def __init__(self, startPoint3D=(0,0,0), endPoint3D=(0,0,0)):
    self.startPoint = startPoint3D
    self.endPoint = endPoint3D
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
    pygame.draw.aaline(tempSurfaceObj, (0, 0, 255),
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

  def draw(self, screen):
    """draw to screen (call .render() before if necessary)"""
    screen.blit(self.surfaceObj, self.rect)



def compute_projection_parameters(newrotation, newelevation, newzoom):
  "changes the camera perspective"
  global rotation, elevation, right, front, up, zoom
  rotation = newrotation
  elevation = newelevation
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




def makeButtons():
  """initialize GUI buttons, returns a list of BUTTONs"""
  buttons = []

  newButton = AddStraightButton("addStraight")
  rect = newButton.surfaceObj.get_rect()
  rect.topright = (WINDOW_SIZE[0],0)
  newButton.setRectangle(rect)
  buttons.append(newButton)

  return buttons



def infoMessage(msg):
  """append a message to the queue and keep the queue at a max length"""
  messageQueue.append(msg)
  if len(messageQueue) > 8:
    messageQueue.popleft()



def selectObjects(obj=[], add=False):
  global selectedObjects
  if not obj:
    selectedObjects = []
  elif isinstance(obj, list):
    if add:
      selectedObjects.extend(obj)
    else:
      selectedObjects = obj
  else:
    if add and obj not in selectedObjects:
      selectedObjects.append(obj)
    else:
      selectedObjects = [obj]



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



def main():
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
  # repeat keypresses as long as the are held down (resend events)
  pygame.key.set_repeat(1, 30)

  # render the initial background
  BGSurfaceObj = render_background(screen)

  # create a small cursor
  cursor_position = [0, 0, 0]
  CursorSurfaceObj = pygame.Surface((1, 1))
  CursorSurfaceObj.fill((0, 0, 0))

  buttons = makeButtons()
  boxSelectionInProgress = False
  boxStartPoint = (0, 0)


  # MAIN LOOP
  running = True
  while running:
    # limit to 30 fps
    clock.tick(30)

    # get all events
    for event in pygame.event.get():
      # quit game if quit event is registered
      if event.type == pygame.QUIT:
        running = False
      elif event.type == pygame.KEYDOWN:
        if event.key == pygame.K_ESCAPE:
          logging.debug("Quitting (ESC key)")
          running = False
      elif event.type == pygame.MOUSEBUTTONDOWN:
        boxSelectionInProgress = True
        boxStartPoint = pygame.mouse.get_pos()
      elif event.type == pygame.MOUSEBUTTONUP:
        boxSelectionInProgress = False
        for button in buttons:
          if button.checkClicked():
            button.activate()
            button.clickAction()
        for obj in objectsList:
          if obj.checkClicked():
            selectObjects(obj)
            infoMessage("Object clicked!")

    pressed_keys = pygame.key.get_pressed()
    rerender = False
    # move cursor
    if pressed_keys[pygame.K_UP]:
      cursor_position[1] += 10
    if pressed_keys[pygame.K_DOWN]:
      cursor_position[1] -= 10
    if pressed_keys[pygame.K_LEFT]:
      cursor_position[0] -= 10
    if pressed_keys[pygame.K_RIGHT]:
      cursor_position[0] += 10
    if pressed_keys[pygame.K_PAGEUP]:
      cursor_position[2] += 10
    if pressed_keys[pygame.K_PAGEDOWN]:
      cursor_position[2] -= 10
    # change camera settings
    if pressed_keys[pygame.K_a]:
      compute_projection_parameters(rotation-ROTATION_ANGULAR_SPEED, elevation, zoom)
      rerender = True
    if pressed_keys[pygame.K_d]:
      compute_projection_parameters(rotation+ROTATION_ANGULAR_SPEED, elevation, zoom)
      rerender = True
    if pressed_keys[pygame.K_w]:
      compute_projection_parameters(rotation, elevation+ELEVATION_ANGULAR_SPEED, zoom)
      rerender = True
    if pressed_keys[pygame.K_s]:
      compute_projection_parameters(rotation, elevation-ELEVATION_ANGULAR_SPEED, zoom)
      rerender = True
    if pressed_keys[pygame.K_HOME]:
      compute_projection_parameters(-45*(pi/180.), -66*(pi/180.), 1.0)
      rerender = True
    if pressed_keys[pygame.K_MINUS]:
      compute_projection_parameters(rotation, elevation, zoom * ZOOM_OUT_SPEED)
      rerender = True
    if pressed_keys[pygame.K_PLUS]:
      compute_projection_parameters(rotation, elevation, zoom * ZOOM_IN_SPEED)
      rerender = True
    if rerender:
      BGSurfaceObj = render_background(screen)
      for o in objectsList:
        o.render()
    render = False


    # render cursor
    screen.blit(BGSurfaceObj, (0, 0))
    test_pixelpos = pixelpos(cursor_position, ORIGIN)
    screen.blit(CursorSurfaceObj, test_pixelpos)

    # render info text at (and about) cursor position (3D -> pixels)
    text = '(%.1f, %.1f, %.1f) -> (%d, %d)'%(cursor_position[0], cursor_position[1], cursor_position[2],
                                             test_pixelpos[0], test_pixelpos[1])
    textObj = pygame.font.SysFont(None, 18).render(text, True, (0, 0, 0))
    textRect = textObj.get_rect()
    textRect.topleft = (test_pixelpos[0]+10, test_pixelpos[1])
    screen.blit(textObj, textRect)

    # render info text about rotation and elevation angles
    text = "Rotation angle = %.2f RAD (ca. %d DEG)" % (rotation, rotation*180./pi)
    textObj = pygame.font.SysFont(None, 18).render(text, True, (0, 0, 0))
    textRect = textObj.get_rect()
    textRect.topleft = (0, 0)
    screen.blit(textObj, textRect)
    text = "Elevation angle = %.2f RAD (ca. %d DEG)" % (elevation, elevation*180./pi)
    textObj = pygame.font.SysFont(None, 18).render(text, True, (0, 0, 0))
    textRect = textObj.get_rect()
    textRect.topleft = (0, 15)
    screen.blit(textObj, textRect)
    lines = ["Use WASD to rotate the camera (isometric projection, camera is at window center).",
             "Move the cursor with the ARROW KEYS and PAGE-UP/DOWN.",
             "Zoom in and out using the + (plus) and - (minus) keys.",
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

    # draw lines to visualize the cursor's position in 3D space
    drawHelpLines(cursor_position, screen)

    # draw objects
    for o in objectsList:
      o.draw(screen)

    # draw selection box and select objects within
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
      selectObjects()
      for obj in objectsList:
        if obj.inRect(selectionBoxRect):
          selectObjects(obj, True)
          infoMessage("Object selected (Box)")

    # mark selected objects:
    print selectedObjects
    for o in selectedObjects:
      markObject(o, screen)

    # draw GUI
    for button in buttons:
      button.draw(screen)
      button.deactivate()

    # actually draw the stuff to screen
    pygame.display.flip()



if __name__ == '__main__':
    main()
