# -*- coding: UTF-8 -*-

import Screen

# a screenmanager class
class ScreenManager:
  # the list of screens known to the manager
  screenList = []
  # the index of the active screen
  activeScreen = 0

  # this method is called every round by the main loop
  # the screenmanager merely decides which screens do have to
  # draw themselves and calls them
  def draw(self, displayDevice):
    self.screenList[self.activeScreen].draw(displayDevice)

  # this method is called every round by the main loop
  # the screenmanager passes the event down to the active screen
  def update(self, event):
    self.screenList[self.activeScreen].update(event)

  def addScreen(self, newScreen, active):
    # add new screen to list
    self.screenList.append(newScreen)
    if (active):
      activeScreen = len(self.screenList) - 1
    
  
