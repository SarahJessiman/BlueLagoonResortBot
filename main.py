import logging
import os
import sys
import random
import re
import datetime
import spacy
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackContext
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
load_dotenv()

# Conversation states
LOCATION, PEOPLE, ROOM_SELECTION, CHECK_IN_DATE, TOTAL_NIGHTS, CULC_TOTAL_COST, CONTACT, DIETARY, SPECIFIC_DIETARY, CONFIRM = range(10)

# Load spaCy's English language model
nlp = spacy.load("en_core_web_sm")

# SentenceTyper and VerbFinder classes

class SentenceTyper(spacy.matcher.Matcher):
    """Derived matcher meant for determining the sentence type"""
    def __init__(self, vocab):
        super().__init__(vocab)
        # Interrogative (question)
        self.add("WH-QUESTION", [[{"IS_SENT_START": True, "TAG": {"IN": ["WDT", "WP", "WP$", "WRB"]}}]])
        self.add("YN-QUESTION",
                 [[{"IS_SENT_START": True, "TAG": "MD"}, {"POS": {"IN": ["PRON", "PROPN", "DET"]}}],
                  [{"IS_SENT_START": True, "POS": "VERB"}, {"POS": {"IN": ["PRON", "PROPN", "DET"]}}, {"POS": "VERB"}]])
        # Imperative (instructions)
        self.add("INSTRUCTION",
                 [[{"IS_SENT_START": True, "TAG": "VB"}],
                  [{"IS_SENT_START": True, "LOWER": {"IN": ["please", "kindly"]}}, {"TAG": "VB"}]])
        # Wish request
        self.add("WISH",
                 [[{"IS_SENT_START": True, "TAG": "PRP"}, {"TAG": "MD"},
                  {"POS": "VERB", "LEMMA": {"IN": ["love", "like", "appreciate"]}}],  # e.g. I'd like...
                  [{"IS_SENT_START": True, "TAG": "PRP"}, {"POS": "VERB", "LEMMA": {"IN": ["want", "need", "require"]}}]])
        # Exclamatory (emotive)
        # Declarative (statements)

    def __call__(self, *args, **kwargs):
        """inspects the first match, and returns the appropriate sentence type handler"""
        matches = super().__call__(*args, **kwargs)
        if matches:
            match_id, _, _ = matches[0]
            if match_id == self.vocab["WH-QUESTION"]:
                return wh_question_handler
            elif match_id == self.vocab["YN-QUESTION"]:
                return yn_question_handler
            elif match_id == self.vocab["WISH"]:
                return wish_handler
            elif match_id == self.vocab["INSTRUCTION"]:
                return instruction_handler
        else:  # either 'cos there's no matches, or we haven't yet got a custom handler
            return generic_handler
        if len(matches) > 1:
            logger.debug(f"NOTE: SentenceTyper actually found {len(matches)} matches.")


class VerbFinder(spacy.matcher.DependencyMatcher):
    """Derived matcher meant for finding verb phrases"""
    def __init__(self, vocab):
        super().__init__(vocab)
        self.add("VERBPHRASE", [
            [{"RIGHT_ID": "root", "RIGHT_ATTRS": {"DEP": "ROOT"}},
             {"LEFT_ID": "root", "REL_OP": ">", "RIGHT_ID": "auxiliary", "RIGHT_ATTRS": {"TAG": "VB"}},
             {"LEFT_ID": "root", "REL_OP": ">", "RIGHT_ID": "modal", "RIGHT_ATTRS": {"TAG": "MD"}}],
            [{"RIGHT_ID": "root", "RIGHT_ATTRS": {"DEP": "ROOT"}},
             {"LEFT_ID": "root", "REL_OP": ">", "RIGHT_ID": "auxiliary", "RIGHT_ATTRS": {"POS": "AUX"}}],
            [{"RIGHT_ID": "root", "RIGHT_ATTRS": {"DEP": "ROOT"}}]
        ])

    def __call__(self, *args, **kwargs):
        """returns the sequence of token ids which constitute the verb phrase"""
        verbmatches = super().__call__(*args, **kwargs)
        if verbmatches:
            if len(verbmatches) > 1:
                logging.debug(f"NOTE: VerbFinder actually found {len(verbmatches)} matches.")
                for verbmatch in verbmatches:
                    logging.debug(verbmatch)
            _, token_idxs = verbmatches[0]
            return sorted(token_idxs)

povs = {
    "I am": "you are",
    "I was": "you were",
    "I'm": "you're",
    "I'd": "you'd",
    "I've": "you've",
    "I'll": "you'll",
    "you are": "I am",
    "you were": "I was",
    "you're": "I'm",
    "you'd": "I'd",
    "you've": "I've",
    "you'll": "I'll",
    "I": "you",
    "my": "your",
    "your": "my",
    "yours": "mine",
    "you": "I",  # as subject, else "me"
    "me": "you",
}
povs_c = re.compile(r'\b({})\b'.format('|'.join(re.escape(pov) for pov in povs)))

# Handlers for different sentence types

def wh_question_handler(nlp, sentence, verbs_idxs):
    """Requires a qualitative answer. For now, very similar to yn_question_handler"""
    logging.debug(f"INVOKING WH-QUESTION HANDLER {verbs_idxs}")
    reply = []
    reply.append(sentence[0].text.lower())  # by definition, the first word is a wh-word
    part = [chunk.text for chunk in sentence.noun_chunks if chunk.root.dep_ == 'nsubj']
    if part:
        reply.append(part[0])
    reply.append(" ".join([sentence[i].text.lower() for i in verbs_idxs]))
    part = [chunk.text for chunk in sentence.noun_chunks if chunk.root.dep_ == 'dobj']
    if part:
        reply.append(part[0])
    reply = re.sub(povs_c, lambda match: povs.get(match.group()), " ".join(reply))
    reply = random.choice(["I don't know ", "I can't say "]) + reply
    reply += random.choice([", but I'll try to find out for you. Please check in with me again later.",
                            ", but perhaps that's something I'd be able to find out for you. Remind me, if I forget.",
                            ". I'll see if I can find out, though. Ask me again sometime."])
    return reply


def yn_question_handler(nlp, sentence, verbs_idxs):
    """Requires a binary answer. For now, very similar to wh_question_handler"""
    logging.debug("INVOKING YN-QUESTION HANDLER")
    reply = []
    part = [chunk.text for chunk in sentence.noun_chunks if chunk.root.dep_ == 'nsubj']
    if part:
        reply.append(part[0])
    reply.append(" ".join([sentence[i].text.lower() for i in verbs_idxs]))
    part = [chunk.text for chunk in sentence.noun_chunks if chunk.root.dep_ == 'dobj']
    if part:
        reply.append(part[0])
    reply = re.sub(povs_c, lambda match: povs.get(match.group()), " ".join(reply))
    reply = random.choice([
        "I don't know whether ",
        "I can't say if ",
    ]) + reply
    reply += random.choice([
        " at this very moment. Let me find out.",
        ". I may have to think about this some more.",
    ])
    return reply


def wish_handler(nlp, sentence, verbs_idxs):
    """Expresses a wish"""
    logging.debug("INVOKING WISH HANDLER")
    reply = sentence.text
    reply = re.sub(povs_c, lambda match: povs.get(match.group()), reply)
    reply = random.choice([
        "Understood: ",
        "Got it: ",
    ]) + reply
    reply += random.choice([
        " I'll see what I can do.",
        "",
    ])
    return reply


def instruction_handler(nlp, sentence, verbs_idxs):
    """Requires action"""
    logging.debug("INVOKING INSTRUCTION HANDLER")
    reply = sentence.text
    reply = re.sub(povs_c, lambda match: povs.get(match.group()), reply)
    reply = random.choice([
        "Understood: ",
        "Got it: ",
    ]) + reply
    reply += random.choice([
        " What do you think about that?",
        " Thanks for sharing.",
    ])
    return reply


def generic_handler(nlp, sentence, verbs_idxs):
    """Requires something else"""
    logging.debug("INVOKING GENERIC HANDLER")
    reply = sentence.text
    reply = re.sub(povs_c, lambda match: povs.get(match.group()), reply)
    return reply

# Telegram Bot handlers

def banter(update, context):
    nlp = spacy.load('en_core_web_sm')
    doc = nlp(update.message.text)
    sentencetyper = SentenceTyper(nlp.vocab)
    verbfinder = VerbFinder(nlp.vocab)

    reply = ''
    for sentence in doc.sents:
        verbs_idxs = verbfinder(sentence.as_doc())
        reply += (sentencetyper(sentence.as_doc()))(nlp, sentence, verbs_idxs)

    update.message.reply_text(reply)
    return


def start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Welcome to Blue Lagoon Resort Chatbot! Please choose your desired resort location:")
    update.message.reply_text("Please reply with Knysna or Port Elizabeth")

    return LOCATION


def location(update: Update, context: CallbackContext) -> int:
    location = update.message.text.lower()
    if location not in ["knysna", "port elizabeth"]:
        update.message.reply_text("Please enter a valid location: Knysna or Port Elizabeth")
        return LOCATION
    context.user_data['location'] = location

    update.message.reply_text("How many people will be checking in?")
    return PEOPLE


def people(update: Update, context: CallbackContext) -> int:
    try:
        people = int(update.message.text)
        if not 1 <= people <= 8:
            update.message.reply_text("Please enter a valid number of people (1 to 8).")
            return PEOPLE
        context.user_data['people'] = people

        update.message.reply_text("Here is a list of our rooms & rates:"
                                  "\n<b>Blue Hut</b> | 2 people | R450.00 per night"
                                  "\n<b>Lagoon House Boat</b> | 4 people | R1200.00 per night"
                                  "\n<b>Tropical House</b> | 8 people | R2150.00 per night",
                                  parse_mode="HTML")

        if 1 <= people <= 2:
            update.message.reply_text("The 'Blue Hut' OR 'Lagoon House Boat' is available for you!")
            update.message.reply_text("Please reply with 'Blue Hut' OR 'Lagoon House Boat' to confirm your choice.")
            return ROOM_SELECTION
        elif 2 <= people <= 4:
            update.message.reply_text("The 'Lagoon House Boat' OR 'Tropical House' is available for you!")
            update.message.reply_text("Please reply with 'Lagoon House Boat' OR 'Tropical House' to confirm your choice.")
            return ROOM_SELECTION
        elif 4 <= people <= 8:
            update.message.reply_text("The 'Tropical House' is available for you!")
            update.message.reply_text("Please reply with 'Tropical House' to confirm your choice.")
            return ROOM_SELECTION
        else:
            update.message.reply_text("Sorry, we don't have rooms available for that number of people. Please enter valid info")
            return PEOPLE

    except ValueError:
        update.message.reply_text("Please enter a valid number of people (1 to 8).")
    return PEOPLE


def room_selection(update: Update, context: CallbackContext) -> int:
    room_choice = update.message.text.lower()

    if room_choice == "blue hut":
        context.user_data['room'] = "Blue Hut"
    elif room_choice == "lagoon house boat":
        context.user_data['room'] = "Lagoon House Boat"
    elif room_choice == "tropical house":
        context.user_data['room'] = "Tropical House"
    else:
        update.message.reply_text("Invalid room choice. Please choose one of the available rooms.")
        return ROOM_SELECTION

    update.message.reply_text(f"You have selected the {context.user_data['room']}.")
    # update.message.reply_text("Please provide number of nights you wish to stay.")
    # return TOTAL_NIGHTS

    # Ask for check-in date
    update.message.reply_text("Please provide the check-in date (YYYY-MM-DD).")
    return CHECK_IN_DATE


def check_in_date_input(update: Update, context: CallbackContext) -> int:
    try:
        check_in_date = datetime.datetime.strptime(update.message.text, '%Y-%m-%d').date()
        context.user_data['check_in_date'] = check_in_date

        update.message.reply_text("Please provide number of nights you wish to stay.")
        return TOTAL_NIGHTS

        # return end_conversation(update, context)

    except ValueError:
        update.message.reply_text("Please enter a valid date in the format YYYY-MM-DD.")
        return CHECK_IN_DATE


def calculate_total_cost(room, nights):
    room_details = {
        "Blue Hut": {"capacity": 2, "cost_per_night": 450.00},
        "Lagoon Boat": {"capacity": 4, "cost_per_night": 1200.00},
        "Tropical House": {"capacity": 8, "cost_per_night": 2100.00},
    }

    if room in room_details:
        cost_per_night = room_details[room]["cost_per_night"]
        total_cost = cost_per_night * nights
        return total_cost
    else:
        return None


def total_nights(update: Update, context: CallbackContext) -> int:
    try:
        total_nights = int(update.message.text)
        if total_nights <= 0:
            update.message.reply_text("Please enter a valid number of nights.")
            return TOTAL_NIGHTS
        context.user_data['total_nights'] = total_nights

        room = context.user_data.get('room')
        if room:
            total_cost = calculate_total_cost(room, total_nights)
            if total_cost is not None:
                update.message.reply_text(f"The total cost for {total_nights} nights in the {room} is R{total_cost:.2f}")
            else:
                update.message.reply_text("Invalid room selection. Please start the conversation again.")
                return start(update, context)

        update.message.reply_text("Please provide your contact information (Phone Number).")
        return CONTACT

    except ValueError:
        update.message.reply_text("Please enter a valid number of nights.")
        return TOTAL_NIGHTS


def contact(update: Update, context: CallbackContext) -> int:
    contact_info = update.message.text
    # Validate contact number format (10 digits)
    if not re.match(r'^\d{10}$', contact_info):
        update.message.reply_text("Please enter a valid 10-digit contact number.")
        return CONTACT
    context.user_data['contact'] = contact_info

    update.message.reply_text("Do you have any dietary requirements for food? (Yes/No)")
    return DIETARY


def dietary(update: Update, context: CallbackContext) -> int:
    dietary_requirements = update.message.text.lower()
    context.user_data['dietary'] = dietary_requirements
    if dietary_requirements == 'yes':
        update.message.reply_text("Please specify your dietary requirements.")
        return SPECIFIC_DIETARY
    else:
        return end_conversation(update, context)


def specific_dietary(update: Update, context: CallbackContext) -> int:
    specific_dietary_requirements = update.message.text
    context.user_data['specific_dietary'] = specific_dietary_requirements

    return end_conversation(update, context)


def end_conversation(update: Update, context: CallbackContext) -> int:

    check_in_date = context.user_data.get('check_in_date')  # Retrieve the check-in date from user data

    total_nights = context.user_data.get('total_nights')  # Retrieve the total nights from user data
    # Call the calculate_total_cost function
    total_cost = calculate_total_cost(context.user_data['room'], total_nights)
    if total_cost is not None:
        user_info = (
            # Display the collected information to the user
            f"Location: {context.user_data['location']}\n"
            f"People: {context.user_data['people']}\n"
            f"Room: {context.user_data['room']}\n"
            f"Check-in Date: {context.user_data['check_in_date']}\n"
            f"Total Nights: {total_nights}\n"
            f"Total Cost: R{total_cost:.2f}\n"
            f"Contact: {context.user_data['contact']}\n"
            f"Dietary Requirements: {context.user_data['dietary']}\n"
        )
        if context.user_data.get('specific_dietary'):
            user_info += f"Specific Dietary Requirements: {context.user_data['specific_dietary']}\n"
        update.message.reply_text(f"Thank you for providing the following information:\n\n{user_info}")
        update.message.reply_text("Is the information correct? (Yes/No)")

        return CONFIRM
    else:
        update.message.reply_text("Invalid room selection. Please start the conversation again.")
        return start(update, context)


# Define the generate_reference_number function
def generate_reference_number():
    return str(random.randint(100000, 999999))


def confirm(update: Update, context: CallbackContext) -> int:
    response = update.message.text.lower()

    # Generate a random reference number
    reference_number = generate_reference_number()

    if response == 'yes':
        update.message.reply_text("Great! Thank you for your information your booking has been confirmed.")
        update.message.reply_text(f"Your Booking Reference Number: {reference_number}\n")

    else:
        update.message.reply_text("Please provide the correct information for any incorrect details.")
        return start(update, context)

    return ConversationHandler.END


def correct(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Please provide the correct information for the respective question.")
    return start(update, context)


def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Conversation cancelled.")
    return ConversationHandler.END


def help(update, context):
    """what situations give rise to a request such as this?"""
    update.message.reply_text("I strongly suggest that you read the manual.")
    return

# Main function

def main():
    updater = Updater(token='6426240467:AAG4WKGO_duiPbByBa_dEfhW9Ha7Az3fVSg', use_context=True)
    dispatcher = updater.dispatcher

    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            LOCATION: [MessageHandler(Filters.text & ~Filters.command, location)],
            PEOPLE: [MessageHandler(Filters.text & ~Filters.command, people)],
            ROOM_SELECTION: [MessageHandler(Filters.text & ~Filters.command, room_selection)],
            CHECK_IN_DATE: [MessageHandler(Filters.text & ~Filters.command, check_in_date_input)],
            TOTAL_NIGHTS: [MessageHandler(Filters.text & ~Filters.command, total_nights)],
            CULC_TOTAL_COST: [MessageHandler(Filters.text & ~Filters.command, calculate_total_cost)],
            CONTACT: [MessageHandler(Filters.text & ~Filters.command, contact)],
            DIETARY: [MessageHandler(Filters.text & ~Filters.command, dietary)],
            SPECIFIC_DIETARY: [MessageHandler(Filters.text & ~Filters.command, specific_dietary)],
            CONFIRM: [MessageHandler(Filters.regex(r'^Yes$|^No$'), confirm)],
        },

        fallbacks=[
            CommandHandler('cancel', cancel),
            MessageHandler(Filters.text & ~Filters.command, confirm),
        ],
    )
    # Add the ConversationHandler to the dispatcher
    dispatcher.add_handler(conversation_handler)

    # Start the bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()