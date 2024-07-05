You can start a server using 

python3 server.py {SERVER_NAME}

where SERVER_NAME can be one of Bailey, Bona, Campbell, Clark, Jaquez. 

In the python script itself, you many want to update the server ports in order to match server ports that you want to use. 
The file provided simply starts the server, and the user needs their own way to listen to the server. For my testing purposes, I used "nc localhoust {port number}" in order to listen to the servers.

You also need to replace the variable "GOOGLE_PLACES_API_KEY" in the python script with your own Google Places API key. I have removed mine for security reasons.

