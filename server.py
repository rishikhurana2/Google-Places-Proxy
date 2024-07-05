import asyncio
import argparse
import sys
import re
import time
import aiohttp
import json

# Mapping between Servers and Ports
SERVER_PORTS = {
    "Bailey" : 21257,
    "Bona" : 21258,
    "Campbell" : 21259,
    "Clark" : 21260,
    "Jaquez" : 21261
}

# Mapping between servers and array of servers
# Each array of if "Campbell" --> ["Bailey", "Bona", "Jaquez"], then Campbell communicates with Baily, Bona, and Jaquez
# Term: if Campbell --> Bailey, then Campbell and Bailey are "friends" (Baily --> Campbell must also be true)
FRIENDS = {
    "Bailey" : ["Bona", "Campbell"],
    "Bona" : ["Bailey", "Clark", "Campbell"],
    "Campbell" : ["Bailey", "Bona", "Jaquez"],
    "Clark" : ["Jaquez", "Bona"],
    "Jaquez" : ["Clark", "Campbell"]
}

# mapping between a client and their [server, location, message send time, time diff between message send and message received]
# index 0 stores the initial zerver, index 1 stores the location, index 2 stores the time the client sent the message, index 4 stores the time difference

CLIENT_INFO = {}

GOOGLE_PLACES_API_KEY = "API KEY"  # Google places API Key Here (removed for security)

parser = argparse.ArgumentParser()
parser.add_argument("server_name", help="Name of the server you would like to start")
server_name = parser.parse_args().server_name
if (server_name not in SERVER_PORTS):
    raise argparse.ArgumentTypeError("Please enter a valid ID (Bailey, Bona, Campbell, Clark, Jaquez)")
port = SERVER_PORTS[server_name]


async def main():
    server = await asyncio.start_server(handle_connection, '127.0.0.1', port=port)
    async with server:
        await server.serve_forever()

def log_msg(msg):
    f = open(server_name + "_Log.txt", 'a')
    f.write(msg)
    f.write("\n")
    f.close()

async def send_message_to_client(message, writer):
    log_msg(f"Sent '{message.strip()}' to client")
    writer.write((message.strip() + '\n').encode())
    await writer.drain()


# send a message to the servers friends (flooding algorithm)
# sender_name : the host server sending a message
# message : the message the host wants to send
async def send_message_to_friends(sender_name, message):
    friends = FRIENDS[sender_name]
    for friend in friends:
        friend_port = SERVER_PORTS[friend]
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", friend_port)
            log_msg(f"Connected with server '{friend}' to send '{message}'")
            writer.write(message.encode())
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            log_msg(f"Closed connection with server '{friend}'")
        except:
            log_msg(f"Tried connecting with server '{friend}' to send '{message}' but failed to connect")

async def handle_connection(reader, writer):
    while (not (reader.at_eof())):
        data = await reader.readline()
        msg_receive_time = "%.9f" % time.time()
        received_msg = data.decode()
        command = received_msg.split()
        if (len(command) == 0):
            log_msg(f"Received '{received_msg.strip()}' from client")
            await send_message_to_client("? ", writer)
        elif (   (command[0] not in ["IAMAT", "WHATSAT", "AT"] )
                or ( (command[0] in ["IAMAT", "WHATSAT"]) and len(command) != 4)
                or ( (command[0] == "AT") and len(command) != 6)
                or ( (command[0] == "WHATSAT") and ( int(command[2]) < 0 or int(command[2]) > 50 or int(command[3]) < 0 or int(command[3]) > 20 ) )
            ):
            # can assume IAMAT coordinates and timstamp is valid (no need to check for it)
            log_msg(f"Received '{received_msg.strip()}' from client")
            await send_message_to_client("? " + received_msg, writer)
        elif (command[0] == "IAMAT"):
            log_msg(f"Received '{received_msg.strip()}' from client")

            client = command[1]
            client_loc = command[2]
            client_send_time = command[3]

            delta_time = get_delta_time(client_send_time, msg_receive_time)

            # need to store the client location in our map
            CLIENT_INFO[client] = [server_name, client_loc, client_send_time, delta_time]

            # sent the AT command to the client
            await send_message_to_client(f"AT {server_name} {delta_time} {client} {client_loc} {client_send_time}", writer)

            # now we need to tell everyone else where the client is
            await send_message_to_friends(server_name, f"AT {server_name} {delta_time} {client} {client_loc} {client_send_time}")

        elif (command[0] == "AT"): # for when another client sends an AT command to friends

            # gather the info received in the message

            initial_server = command[1]
            client_delta_time = command[2]
            client = command[3]
            client_loc = command[4]
            client_send_time = command[5]

            # If the server has received more updated info, then update database and tell friends
            if ( (client not in CLIENT_INFO) or (client_send_time > CLIENT_INFO[client][2])):
                # update the server's client info database
                CLIENT_INFO[client] = [initial_server, client_loc, client_send_time, client_delta_time]
                # propogate the new client info to friends

                log_msg(f"Received '{received_msg.strip()}' via flooding")

                await send_message_to_friends(server_name, f"AT {initial_server} {client_delta_time} {client} {client_loc} {client_send_time}")
            else:
                log_msg(f"Received '{received_msg.strip()}' via flooding but didn't propogate message (current database more updated)")
        
        elif (command[0] == "WHATSAT"):
            log_msg(f"Received '{received_msg.strip()}' from client")

            client_query = command[1]


            if (client_query not in CLIENT_INFO):
                await send_message_to_client(f"Client '{client_query}' not in database", writer)
            else:
                google_format_client_loc = google_format_coords(CLIENT_INFO[client_query][1])            
                r = command[2]
                limit = command[3]
    
                query_url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?key={GOOGLE_PLACES_API_KEY}&location={google_format_client_loc}&radius={r}"
        
                most_recent_AT = f"AT {CLIENT_INFO[client_query][0]} {CLIENT_INFO[client_query][3]} {client_query} {CLIENT_INFO[client_query][1]} {CLIENT_INFO[client_query][2]}\n"
                
                async with aiohttp.ClientSession() as query_sesh:
                    async with query_sesh.get(query_url) as query:
                        resp = await query.json()
                        if (len(resp) > int(limit)): # limit the number of results to the limit specified by the client
                            resp["results"] = resp["results"][: int(limit)] 
                        resp = json.dumps(resp, indent=3) # make the response a json string so that it can be transmitted to the client
                        resp.strip('\n').replace('\n\n', '\n') # remove trailing new lines and replace any double new line with a single new line
                        
                # can't call send_message_to_client() because WHATSAT has a different format for response (need two '\n' characters)
                msg = most_recent_AT + resp + '\n\n'

                log_msg(f"Sent '{msg}' to client")
                writer.write(msg.encode())
                await writer.drain()


    writer.close()

def get_delta_time(send_time, receive_time):
    delta = float(receive_time) - float(send_time)
    if (delta > 0):
        return "+%.9f" % delta # if the time is positve, return with positive sign and formatting
    return "%.9f" % delta # if the time is negative, return with formatting

# takes formate of the coords specified by project and turns it into the coords that google places takes
# google takes in form "latitude,longitude"
def google_format_coords(coords):
    split_index = -1
    for i in range(1, len(coords)): 
        if (coords[i] == "+" or coords[i] == "-"): # once we encounter the +/- that is after the first one, then we split here
            split_index = i

    return f"{coords[:split_index]},{coords[split_index:]}"

if __name__ == "__main__":
    asyncio.run(main())
