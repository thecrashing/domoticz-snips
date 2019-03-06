#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import configparser
from hermes_python.hermes import Hermes
from hermes_python.ffi.utils import MqttOptions
from hermes_python.ontology import *

import io
import requests
import json
import jellyfish

MAX_JARO_DISTANCE = 0.4

CONFIGURATION_ENCODING_FORMAT = "utf-8"
CONFIG_INI = "config.ini"

class SnipsConfigParser(configparser.SafeConfigParser):
    def to_dict(self):
        return {section : {option_name : option for option_name, option in self.items(section)} for section in self.sections()}


def read_configuration_file(configuration_file):
    try:
        with io.open(configuration_file, encoding=CONFIGURATION_ENCODING_FORMAT) as f:
            conf_parser = SnipsConfigParser()
            conf_parser.readfp(f)
            return conf_parser.to_dict()
    except (IOError, configparser.Error) as e:
        return dict()


def getSceneNames(conf,myListSceneOrSwitch):
    myURL="http://"+conf.get("secret").get("domoticz_ip")+':'+conf.get("secret").get("domoticz_port")+'/json.htm?type=scenes'
    response = requests.get(myURL)
    jsonresponse = response.json()#json.load(response)
    for scene in jsonresponse["result"]:
        myName=scene["Name"].encode('utf-8')
        myListSceneOrSwitch[(scene["idx"])] = {'Type':'switchscene','Name':myName}
    return myListSceneOrSwitch
def getSwitchNames(conf,myListSceneOrSwitch):
    myURL="http://"+conf.get("secret").get("domoticz_ip")+':'+conf.get("secret").get("domoticz_port")+'/json.htm?type=command&param=getlightswitches'
    response = requests.get(myURL)
    jsonresponse = response.json()#json.load(response)
    for sw in jsonresponse["result"]:
        myName=sw["Name"].encode('utf-8')
        myListSceneOrSwitch[(sw["idx"])] = {'Type':'switchlight','Name':myName}

    return myListSceneOrSwitch
    
    
def BuildActionSlotList(intent):

    jintent = intent.slots.toDict()
    intentSwitchList=list()
    intentSwitchActionList=list()
    intentSwitchState='On' #by default if no action
    #for mySlot in jintent:#["slots"]:
#    for (slot_value, slot) in intent.slots.items():
#        jintent = slot.toDict()
#        print(jintent)


    for (slot_value, slot) in intent.slots.items():
        if slot_value=="Action":
            if len(intentSwitchList)>0:
                for mySwitch in intentSwitchList:
                    intentSwitchActionList.append({'Name':mySwitch,'State':intentSwitchState})
            if slot[0].slot_value.value.value=="TurnOn":
                intentSwitchState='On'
            else :
                intentSwitchState='Off'   
            intentSwitchList=list()
        elif slot_value=="Interrupteur":
            for slot_value2 in slot.all():
                intentSwitchList.append(slot_value2.value)
    
    for mySwitch in intentSwitchList:
        intentSwitchActionList.append({'Name':mySwitch,'State':intentSwitchState})
    return intentSwitchActionList

def curlCmd(idx,myCmd,myParam,conf):
    command_url="http://"+conf.get("secret").get("domoticz_ip")+':'+conf.get("secret").get("domoticz_port")+'/json.htm?type=command&param='+myParam+'&idx='+str(idx)+'&switchcmd='+myCmd
    ignore_result = requests.get(command_url)

    
def ActionneEntity(name,action,myListSceneOrSwitch,conf):
#derived from nice work of https://github.com/iMartyn/domoticz-snips
    lowest_distance = MAX_JARO_DISTANCE
    lowest_idx = 65534
    lowest_name = "Unknown"
    MyWord=name
    for idx,scene in myListSceneOrSwitch.items():
#        print(str(scene['Name'],'utf-8'))
        distance = 1-jellyfish.jaro_distance(str(scene['Name'],'utf-8'), MyWord)
    #    print "Distance is "+str(distance)
        if distance < lowest_distance:
    #        print "Low enough and lowest!"
            lowest_distance = distance
            lowest_idx = idx
            lowest_name = scene['Name']
            lowest_Type= scene['Type']
    if lowest_distance < MAX_JARO_DISTANCE:
        #print (lowest_Type)
        print(lowest_name)
        #print(lowest_idx)
        curlCmd(lowest_idx,action,lowest_Type,conf)
        return True
        #hermes.publish_end_session(intent_message.session_id, "j'allume "+lowest_name)
    else:
        return False
    

def subscribe_intent_callback(hermes, intentMessage):

     
    conf = read_configuration_file(CONFIG_INI)
    #a=IntentClassifierResult(intentMessage).intent_name
    hermes.publish_continue_session(intentMessage.session_id, "OK",["felinh:IntentLumiere","felinh:IntentOrdreDivers"])
    if len(intentMessage.slots.OrdreDivers) > 0:
     print('---------OrdreDivers----------')
     action_wrapperOrdreDirect(hermes, intentMessage, conf)
    else:
     print('---------Ordre Action----------')
     action_wrapperOrdre(hermes, intentMessage, conf)

def action_wrapperOrdreDirect(hermes, intentMessage, conf):
    myListSceneOrSwitch=dict()
    myListSceneOrSwitch= getSceneNames(conf,myListSceneOrSwitch)
    actionText = "{}".format(str(intentMessage.slots.OrdreDivers.first().value))
    print("actionText "+actionText)
    MyAction=ActionneEntity(actionText.decode("utf-8"),'On',myListSceneOrSwitch,conf)
    result_sentence = "OK pour {}".format(str(actionText))  # The response that will be said out loud by the TTS engine.

    if MyAction : 
        hermes.publish_end_session(intentMessage.session_id, result_sentence)
    else:
        print("pas d action")
        hermes.publish_end_session(intentMessage.session_id, "desole, je ne pas m executer ")
    

def action_wrapperOrdre(hermes, intentMessage, conf):
    myListSceneOrSwitch=dict()
    myListSceneOrSwitch= getSceneNames(conf,myListSceneOrSwitch)
    myListSceneOrSwitch= getSwitchNames(conf,myListSceneOrSwitch)
    intentSwitchActionList=BuildActionSlotList(intentMessage)
    actionText=""
    myAction = True
    for intentSwitchAction in intentSwitchActionList:
        myAction=myAction and ActionneEntity(intentSwitchAction["Name"],intentSwitchAction["State"],myListSceneOrSwitch,conf)
        if intentSwitchAction["State"]=="On": 
            texte="J'allume"
        else:
            texte="J'éteins "
        actionText='{}, {} {}'.format(actionText,texte,str(intentSwitchAction["Name"]))
    if myAction : 
        hermes.publish_end_session(intentMessage.session_id, actionText)
    else:
        hermes.publish_end_session(intentMessage.session_id, "desolé, je ne pas m'executer ")
    


if __name__ == "__main__":
    mqtt_opts = MqttOptions()
    with Hermes(mqtt_options=mqtt_opts) as h:
        h.subscribe_intent("felinh:IntentLumiere", subscribe_intent_callback)\
        .subscribe_intent("felinh:IntentOrdreDivers", subscribe_intent_callback)\
        .start()
