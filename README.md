# BlueLagoonResortBot
### Welcome to Blue Lagoon Bot:palm_tree:

I have developed a chat bot that allows you to make a booking at our Blue Lagoon Resort. My chatbot will prompt the user for all their required information based on their specified perferences. This infomration will then be used to make a booking at our resort and generate a reference number which customers will use upon arrival to the resort. This makes the booking process quick and easy, saving our staff time to work on other important tasks while new bookings can still continue.

### Instructions
1. Start - To start a conversation with our chatbot type /start
2. Location - You will be promted to reply with the desired location as we have a resort in Knysna and Port Elizabeth.
3. Number of people - Reply with the number of people checking in.
4. Room - A list of our rooms and rates will be displayed. The bot will list the rooms that are available to you based on your previous reply. You can then reply with your desired choice out of the rooms that are available to you.
5. Check-in Date - Reply with the date you wish to check-in to the resort (Type in format provided).
6. Number of nights - Reply with the number of nights you wish to stay. A price will then be generated based on your choice of room and number of nights.
7. Contact details - Reply with your 10-digit cell phone number.
8. Dietry Requirements - Reply with any specific dietry requirements if necessary (eg. No shell fish).
9. Summary - A summary of your information will be made visable with which you can check and confirm the info is correct.
10. Confirmation - The bot will generate a new refernce number to confirm your booking.

### Limitations
When the BlueLagoonBot encounters anything unexpected it will notify the user that the reply is invalid weither it be a spelling mistake or invalid information. It will then allow you to reply with the correct information and carry on with the remainder of the chat. The bot will then use the updated correct info. The bot is not case sensitive and I have put limitations in place to ensure only valid information can be entered such as:

- Choosing only a valid location that is listed.
- Ensuring the user can only stay in a hut/ house that can accommodate the capacity of people.
- Ensuring their check-in date is entered in the valid date format.
- Ensuring the cell number is 10-digits long.
- Providing an overall summary of their information entered to allow them to confirm their booking details are correct before confirming and receiving a reference number.
- If they have made a mistake or wish to make changes to their information they can confirm that their info is incorrect and allow them to restart the process.
