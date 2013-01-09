# -*- coding: UTF-8 -*-

import pygame
from Screen import Screen

# a class representing the menu of the game
class Menu(Screen):
  selectedItem = 0
  # constructor
  def __init__(self):
    # initialize a basic font
    self.basicFont = pygame.font.SysFont(None, 48)

  # the update method with handles events
  def update(self, event):
    # handle keydown events
    if event.type == pygame.KEYDOWN:
      if event.key == pygame.K_DOWN:
        self.selectedItem += 1
        if self.selectedItem == 2:
          self.selectedItem = 0
      if event.key == pygame.K_UP:
        self.selectedItem -= 1
        if self.selectedItem < 0:
          self.selectedItem = 1
    return;

  # the draw method of the Menu
  def draw(self, displayDevice):
    # set up the text
    displayDevice.fill((0, 0, 150))
    text = self.basicFont.render('Mayday', True, (255, 255, 255), (0, 0, 255))
    textRect = text.get_rect()
    textRect.centerx = displayDevice.get_rect().centerx
    textRect.centery = 100
    displayDevice.blit(text, textRect)

    # display menu items
    if self.selectedItem == 1:
      gameColor = (255, 255, 255)
      optionColor = (0, 0, 0)
    else:
      gameColor = (0, 0, 0)
      optionColor = (255, 255, 255)
    
    text = self.basicFont.render('Start game', True, gameColor, (0, 0, 255))
    textRect = text.get_rect()
    textRect.centerx = 100
    textRect.centery = 150
    displayDevice.blit(text, textRect)
    
    text = self.basicFont.render('Options', True, optionColor, (0, 0, 255))
    textRect = text.get_rect()
    textRect.centerx = 100
    textRect.centery = 250
    displayDevice.blit(text, textRect) 

    return;
