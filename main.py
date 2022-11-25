import datetime
import hashlib
import json
import time

from spade import quit_spade
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, PeriodicBehaviour
from spade.message import Message
from loguru import logger as log


class AgentsCommunications(Agent):
    list_message = {}
    counter: int = 0
    counter_message: int = 0
    class RecvBehav(CyclicBehaviour):
        async def run(self):
            # wait for a message for 10 seconds
            msg = await self.receive(timeout=10)
            if msg:
                log.debug(f"{self.agent.jid} <- content: {msg.body}")
                message = json.loads(msg.body)
                await  self.process(message)
            else:
                log.info(f"{self.agent.jid} <- 10 seconds")
                # self.kill()

        async def process(self, message):
            if "status" in message:
                neighbor = self.get("neighbor")
                if message['status'] == "start":
                    if str(self.agent.jid) not in self.agent.list_message:
                        self.agent.list_message[str(self.agent.jid)] = {}
                    if message["token"] in self.agent.list_message[str(self.agent.jid)]:
                        message['status'] = "end"
                        await self.custom_send(neighbor.index(message['from']), message)
                        return
                    if str(self.agent.jid) == str(message['email']):
                        log.info(f"{str(self.agent.jid)} <- {message['message']}  success {message['token']} ")
                        message['status'] = "success"
                        await self.custom_send(neighbor.index(message['from']), message)
                    elif str(message['email']) in neighbor:
                        message['status'] = "process"
                        await self.custom_send(neighbor.index(message['from']), message)
                        self.agent.list_message[str(self.agent.jid)][message['token']] = message
                        message['status'] = "start"
                        await self.custom_send(neighbor.index(message['email']), message)
                    elif 1 < len(neighbor):
                        message['status'] = "process"
                        await self.custom_send(neighbor.index(message['from']), message)
                        self.agent.list_message[str(self.agent.jid)][message['token']] = message
                        message['status'] = "start"
                        await self.custom_send(neighbor.index(neighbor[0]), message)
                    else:
                        message['status'] = "end"
                        await self.custom_send(neighbor.index(message['from']), message)
                elif message['status'] == "process":
                    if message["token"] in self.agent.list_message[str(self.agent.jid)]:
                        message_local = self.agent.list_message[str(self.agent.jid)][message["token"]]
                        message_local["status"] = "process"
                elif message['status'] == "end":
                    if message["token"] in self.agent.list_message[str(self.agent.jid)]:
                        message_local = self.agent.list_message[str(self.agent.jid)][message["token"]]
                        email_id = message_local['neighbor']
                        if email_id == len(neighbor)-1:
                            log.error("Email not found")
                            self.agent.list_message[str(self.agent.jid)][message["token"]]['status'] = "end"
                            message['status'] = "end"
                            await self.custom_send(neighbor.index(message_local['from']), message)
                            return
                        else:
                            email_id = email_id + 1
                            message_local['neighbor'] = email_id
                            message['status'] = "start"
                            await self.custom_send(email_id, message)
                elif message['status'] == "success":
                    if message["token"] in self.agent.list_message[str(self.agent.jid)]:
                        message_local = self.agent.list_message[str(self.agent.jid)][message["token"]]
                        if message_local["from"] == "root":
                            message_local["status"] = "success"
                            log.info(f"{str(self.agent.jid)} <- success {message['token']}")
                            log.debug(self.agent.list_message[str(self.agent.jid)][message["token"]])
                        else:
                            message_local["status"] = "success"
                            await self.custom_send(neighbor.index(message_local['from']), message)

                else:
                    log.error(f"error message not type status {message}")
            else:
                log.error(f"error message not status {message}")

        async def on_end(self):
            print(self.agent.counter_message)
            await self.agent.stop()

        async def custom_send(self, id_email, object):
            neighbor = self.get("neighbor")
            object["to"] = neighbor[id_email]
            object_copy = object.copy()
            object_copy["from"] = str(self.agent.jid)
            object['neighbor'] = id_email
            msg = Message(
                to=neighbor[id_email],
                body=json.dumps(object_copy)
            )
            self.agent.counter_message += 1
            await self.send(msg)

    class InformBehav(PeriodicBehaviour):

        async def run(self):

            if str(self.agent.jid) not in self.agent.list_message:
                self.agent.list_message[str(self.agent.jid)] = {}
            log.debug(f"{self.agent.jid} Periodic")
            for message in self.agent.list_message[str(self.agent.jid)].values():

                if "status" in message:
                    if message['status'] == "start":
                        log.debug(f"{self.agent.jid} Periodic start {message['token']}")
                    elif message['status'] == "process":
                        log.debug(f"{self.agent.jid} Periodic process {message['token']}")
                    elif message['status'] == "end":
                        pass
                    elif message['status'] == "success":
                        pass
                    else:
                        log.error(f"error message not status {message} {message['token']}")
                else:
                    log.info(f"{str(self.agent.jid)} -> {message['message']}  start {message['token']}")
                    message['status'] = "start"
                    await self.custom_send(0, message)

        async def custom_send(self, id_email, object):
            neighbor = self.get("neighbor")
            object["to"] = neighbor[id_email]
            object_copy = object.copy()
            object_copy["from"] = str(self.agent.jid)
            object['neighbor'] = id_email
            msg = Message(
                to=neighbor[id_email],
                body=json.dumps(object_copy)
            )
            self.agent.counter_message += 1
            await self.send(msg)

        async def on_end(self):
            print(self.agent.counter_message)
            await self.agent.stop()

        async def on_start(self):
            pass

    def create_token(self, email, message):
        str_temp = f"{str(self.counter)} {str(self.jid)} {email} {message}"
        token = str(hashlib.md5(str_temp.encode('utf-8')).hexdigest())
        return token

    def my_start(self, email, message):
        token = self.create_token(email, message)
        if str(self.jid) not in self.list_message:
            self.list_message[str(self.jid)] = {}
        self.list_message[str(self.jid)][token] = {
            "from": "root",
            "email": email,
            "message": message,
            "token": token
        }
        self.counter += 1

    async def my_process(self):
        pass

    async def my_end(self):
        pass

    # Setting up the behavior
    async def setup(self):
        a = self.RecvBehav()
        self.add_behaviour(a)
        start_at = datetime.datetime.now() + datetime.timedelta(seconds=5)
        b = self.InformBehav(period=2, start_at=start_at)
        self.add_behaviour(b)


if __name__ == "__main__":
    log.info("Agents start")

    node_1 = AgentsCommunications("user1@hurmat", "user1@hurmat")
    node_1.set("neighbor", ["user2@hurmat", "user3@hurmat"])
    future_1 = node_1.start(auto_register=True)

    # Sending message from node 2 to another nodes
    node_2 = AgentsCommunications("user2@hurmat", "user2@hurmat")
    node_2.set("neighbor", ["user1@hurmat"])
    future_2 = node_2.start(auto_register=True)

    #Sending message from node 3 to another nodes
    node_3 = AgentsCommunications("user3@hurmat", "user3@hurmat")
    node_3.set("neighbor", ["user1@hurmat","user4@hurmat"])
    future_3 = node_3.start(auto_register=True)

    #Sending message from node 4 to another nodes
    node_4 = AgentsCommunications("user4@hurmat", "user4@hurmat")
    node_4.set("neighbor",["user3@hurmat","user5@hurmat","user6@hurmat","user7@hurmat",])
    future_4 = node_4.start(auto_register=True)

    # Sending message from node 5 to another nodes
    node_5 = AgentsCommunications("user5@hurmat", "user5@hurmat")
    node_5.set("neighbor", ["user4@hurmat","user6@hurmat",])
    future_5 = node_5.start(auto_register=True)

    # Sending message from node 6 to another nodes
    node_6 = AgentsCommunications("user6@hurmat", "user6@hurmat")
    node_6.set("neighbor", ["user5@hurmat","user4@hurmat",])
    future_6 = node_6.start(auto_register=True)

    # Sending message from node 7 to another nodes
    node_7 = AgentsCommunications("user7@hurmat", "user7@hurmat")
    node_7.set("neighbor", ["user4@hurmat","user8@hurmat",])
    future_7 = node_7.start(auto_register=True)

    # Sending message from node 8 to another nodes
    node_8 = AgentsCommunications("user8@hurmat", "user8@hurmat")
    node_8.set("neighbor", ["user7@hurmat",])
    future_8 = node_8.start(auto_register=True)

    node_1.my_start("user8@hurmat", "hi 8")
    # future_1.result()
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:

            node_2.stop()
            node_1.stop()
            break
    log.info("Agents process finished")
    quit_spade()
