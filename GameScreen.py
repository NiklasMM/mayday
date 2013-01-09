# -*- coding: UTF-8 -*-


# a screen class
class GameScreen(Screen):
  level = None

  def __init__(self, levelFileName):
    # import the level file
    levelModule = __import__(levelFileName)
    self.level = levelModule.Level()
    
  def draw(self, displayDevice):
    pass
