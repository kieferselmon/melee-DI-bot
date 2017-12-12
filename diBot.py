#!/usr/bin/python3
import melee
from melee.enums import Action, Button
import argparse
import signal
import sys
import random
from numpy.random import choice


#This example program demonstrates how to use the Melee API to run dolphin programatically,
#   setup controllers, and send button presses over to dolphin

def check_port(value):
    ivalue = int(value)
    if ivalue < 1 or ivalue > 4:
         raise argparse.ArgumentTypeError("%s is an invalid controller port. \
         Must be 1, 2, 3, or 4." % value)
    return ivalue

def di(controller):
    x = random.randint(0,1)
    print ("DI() IS HAPENING" + str(x))
    controller.tilt_analog(Button.BUTTON_MAIN, 0.5, 0.5)

chain = None

parser = argparse.ArgumentParser(description='Example of libmelee in action')
parser.add_argument('--port', '-p', type=check_port,
                    help='The controller port your AI will play on',
                    default=2)
parser.add_argument('--opponent', '-o', type=check_port,
                    help='The controller port the opponent will play on',
                    default=1)
parser.add_argument('--live', '-l',
                    help='The opponent is playing live with a GCN Adapter',
                    default=True)
parser.add_argument('--debug', '-d', action='store_true',
                    help='Debug mode. Creates a CSV of all game state')
parser.add_argument('--framerecord', '-r', default=False, action='store_true',
                    help='Records frame data from the match, stores into framedata.csv')

args = parser.parse_args()

log = None
if args.debug:
    log = melee.logger.Logger()

framedata = melee.framedata.FrameData(args.framerecord)

#Options here are:
#   "Standard" input is what dolphin calls the type of input that we use
#       for named pipe (bot) input
#   GCN_ADAPTER will use your WiiU adapter for live human-controlled play
#   UNPLUGGED is pretty obvious what it means
opponent_type = melee.enums.ControllerType.UNPLUGGED
if args.live:
    opponent_type = melee.enums.ControllerType.GCN_ADAPTER

#Create our Dolphin object. This will be the primary object that we will interface with
dolphin = melee.dolphin.Dolphin(ai_port=args.port, opponent_port=args.opponent,
    opponent_type=opponent_type, logger=log)
#Create our GameState object for the dolphin instance
gamestate = melee.gamestate.GameState(dolphin)
#Create our Controller object that we can press buttons on
controller = melee.controller.Controller(port=args.port, dolphin=dolphin)

def signal_handler(signal, frame):
    dolphin.terminate()
    if args.debug:
        log.writelog()
        print("") #because the ^C will be on the terminal
        print("Log file created: " + log.filename)
    print("Shutting down cleanly...")
    if args.framerecord:
        framedata.saverecording()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

#Run dolphin and render the output
dolphin.run(render=True)

#Plug our controller in
#   Due to how named pipes work, this has to come AFTER running dolphin
#   NOTE: If you're loading a movie file, don't connect the controller,
#   dolphin will hang waiting for input and never receive it
controller.connect()

#dictionary to store di and associated player success ratio
diDict = {"none" : [0,1], "behind": [0,1], "away" : [0,1], "slight_behind" : [0,1], "slight_away" : [0,1]}

#combo flags
started = 0
regrabs = 0
misses = 0

#Main loop
while True:
    #"step" to the next frame
    gamestate.step()
    if(gamestate.processingtime * 1000 > 12):
        print("WARNING: Last frame took " + str(gamestate.processingtime*1000) + "ms to process.")

    #What menu are we in?
    if gamestate.menu_state == melee.enums.Menu.IN_GAME:
        if args.framerecord:
            framedata.recordframe(gamestate)
        #XXX: This is where your AI does all of its stuff!
        #This line will get hit once per frame, so here is where you read
        #   in the gamestate and decide what buttons to push on the controller
        #if args.framerecord:
            #melee.techskill.upsmashes(ai_state=gamestate.ai_state, controller=controller)
        #else:
            #melee.techskill.multishine(ai_state=gamestate.ai_state, controller=controller)

        #print(gamestate.ai_state.hitstun_frames_left)
        print(gamestate.ai_state.action)
        
        diList = diDict.keys()
        print(diList)
        ratioList = []
        for di in diDict:
            ratioList.append(diDict[di][0]/diDict[di][1])
         
        print(ratioList)
        if(gamestate.ai_state.action in [Action.GRABBED, Action.GRAB_PUMMELED, Action.GRAB_PULL, \
                Action.GRAB_PUMMELED, Action.GRAB_PULLING_HIGH, Action.GRABBED_WAIT_HIGH, \
                Action.PUMMELED_HIGH, Action.THROWN_UP]):

            if started == 1 and prevstate not in [Action.GRABBED, Action.GRAB_PUMMELED, Action.GRAB_PULL, \
                Action.GRAB_PUMMELED, Action.GRAB_PULLING_HIGH, Action.GRABBED_WAIT_HIGH, \
                Action.PUMMELED_HIGH, Action.THROWN_UP]:
                regrabs += 1
            started = 1

            di(controller)
        elif(gamestate.ai_state.hitstun_frames_left <= 0):
            controller.tilt_analog(Button.BUTTON_MAIN, 0.5, 0.5)
            if gamestate.ai_state.action in [Action.FALLING, Action.FALLING_AERIAL, Action.TUMBLING]:
                print("In Here")
                if(controller.prev.button[Button.BUTTON_X]):
                    controller.release_button(Button.BUTTON_X)
                else:
                    controller.press_button(Button.BUTTON_X)

            if started == 1 and gamestate.ai_state.action in [Action.TECH_MISS_UP, Action.TECH_MISS_DOWN, Action.LYING_GROUND_DOWN]:
                misses += 1
                started = 0


        print (started)
        print (regrabs)
        print (misses)
        prevstate = gamestate.ai_state.action
        
    #If we're at the character select screen, choose our character
    elif gamestate.menu_state == melee.enums.Menu.CHARACTER_SELECT:
        melee.menuhelper.choosecharacter(character=melee.enums.Character.FOX,
            gamestate=gamestate, controller=controller, swag=True, start=True)
    #If we're at the postgame scores screen, spam START
    elif gamestate.menu_state == melee.enums.Menu.POSTGAME_SCORES:
        melee.menuhelper.skippostgame(controller=controller)
    #If we're at the stage select screen, choose a stage
    elif gamestate.menu_state == melee.enums.Menu.STAGE_SELECT:
        melee.menuhelper.choosestage(stage=melee.enums.Stage.FINAL_DESTINATION,
            gamestate=gamestate, controller=controller)
    #Flush any button presses queued up
    controller.flush()
    if log:
        log.logframe(gamestate)
        log.writeframe()

