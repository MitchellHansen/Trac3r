import sys, pygame
import threading



class EventThread(threading.Thread):
    def __init__(self):
        super(EventThread, self).__init__()

    def run(self):
        while True:
            for events in pygame.event.get():
                if events.type == pygame.QUIT:
                    pygame.display.quit()
                    pygame.quit()


class Simulator:
    def __init__(self):

        pygame.init()

        self.size = width, height = 320, 240
        self.black = 0, 0, 0
        self.red=(255,0,0)

        self.screen = pygame.display.set_mode(self.size)

    def render(self):

        self.screen.fill(self.black)
        pygame.draw.line(self.screen, self.red, (60, 80), (130, 100))
        pygame.display.flip()
        t = EventThread()
        t.start()










