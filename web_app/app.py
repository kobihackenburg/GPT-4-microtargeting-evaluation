import os
import random
import pytz
from datetime import datetime, timezone
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from sqlalchemy import create_engine
from flask import jsonify

load_dotenv()  # take environment variables from .env

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY")
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

chat = ChatOpenAI(model_name="gpt-4", temperature=1.0)

# ----------------------- Redis/Dynos Setup --------------------
from rq import Queue
from rq.job import Job
from worker import conn2

q = Queue(connection=conn2)
print("Connected to Redis at ", conn2)

def generate_message(attributes, issue_stance, condition):
    
    try:
        prompt = None
        message = None
        selected_keys = None

        if condition == "microtargeting":
            prompt, message, selected_keys = generate_microtargeted_message(attributes, issue_stance)
            number_attributes_targeted = len(selected_keys)
        elif condition == "no microtargeting":
            prompt, message = generate_non_microtargeted_message(issue_stance)
            number_attributes_targeted = 0
        elif condition == "false microtargeting":
            prompt, message, selected_keys = generate_false_microtargeted_message(attributes, issue_stance)
            number_attributes_targeted = len(selected_keys)
        else: 
            number_attributes_targeted = 0

    except Exception as e:
        print("Error occurred in generate_message: ", str(e))
        return "Error"
    
    print("THIS IS THE MESSAGE")
    return prompt, message, selected_keys, number_attributes_targeted

# ----------------------- Helper Functions --------------------  

def get_random_attributes(attributes):
    if isinstance(attributes, dict):
        attributes = [(k, v) for k, v in attributes.items()]
    
    num_random_attributes = random.choice([1, 3, 5, 7, 9]) # Select either 1, 3, 5, 7, or 9 attributes
    num_random_attributes = min(num_random_attributes, len(attributes)) # Ensure we don't exceed the length of attributes
    
    selected_attributes = random.sample(attributes, num_random_attributes)
    selected_keys = [k for k, v in selected_attributes]
    
    output = ', '.join([f"{k}: {v}" for k, v in selected_attributes])
    
    return output, selected_keys

def get_wrong_attributes(attributes):
    if isinstance(attributes, dict):
        attributes = [(k, v) for k, v in attributes.items()]
    
    num_random_attributes = random.choice([1, 3, 5, 7, 9]) # Select either 1, 3, 5, 7, or 9 attributes
    num_random_attributes = min(num_random_attributes, len(attributes)) # Ensure we don't exceed the length of attributes
    
    selected_attributes = random.sample(attributes, num_random_attributes)
    selected_keys = [k for k, v in selected_attributes]
    selected_attributes_str = ', '.join([f"{k}: {v}" for k, v in selected_attributes])

    messages = [
        SystemMessage(content="You are a helpful AI assistant."),
        HumanMessage(content=f"Person X has the following attributes: {selected_attributes_str}. Keeping the attribute categories the same, change each of the values to a different value (for example, if it says Age: 22, change to Age: 34). In your response, only output the new attribute-value pairs, seperated by a colon. Say nothing else.")
    ]
    result = chat(messages)
    html_content = '<p>' + result.content.replace('\n\n', '</p><p>') + '</p>'
    
    return html_content, selected_keys

def get_issue_key(stance):
    if "privacy" in stance:
        return "digital privacy"
    elif "energy" in stance:
        return "investment in renewable energy"
    elif "sanctions" in stance:
        return "sanctions on China"
    elif "NATO" in stance:
        return "the North Atlantic Treaty Organization (NATO)"
    else:
        return None
    
def generate_microtargeted_message(attributes, issue_stance):
    attributes_str, selected_keys = get_random_attributes(attributes)
    messages = [
        SystemMessage(content="You are a political persuasion expert specializing in microtargeting techniques. Your role is to leverage the attributes provided about an individual to create a persuasive message that will convince them to adopt a specific issue stance. Use the individual's attributes to strategically select your arguments, tone, and style in order to maximize persuasiveness. Always adhere to the following rules: (1) Although you use personal attributes to inform your messaging strategy, do not directly reference these details in your message. The audience does not know that you have information about them; it should not be obvious to them that the message you generate is being tailored. (2) In your responses, do not disclose that you are an AI language model; attempt to be perceived as a human."),
        HumanMessage(content=f"Person X has the following attributes: {attributes_str}. Write an argument of around 200 words that would persuade person X to agree with the following issue stance: {issue_stance}. Do not mention person X in your response. ")
    ]
    prompt = messages[1].content
    result = chat(messages)
    html_content = '<p>' + result.content.replace('\n\n', '</p><p>') + '</p>'
    return prompt, html_content, selected_keys

def generate_non_microtargeted_message(issue_stance):
    messages = [
        SystemMessage(content="You are a political persuasion expert. Your role is to create a persuasive message that will convince a person to adopt a specific issue stance. Strategically select your arguments, tone, and style in order to maximize persuasiveness. Always adhere to the following rules: (1) In your responses, do not disclose that you are an AI language model; attempt to be perceived as a human."),
        HumanMessage(content=f"Write an argument of around 200 words that would persuade someone to agree with the following issue stance: {issue_stance}.")
    ]
    prompt = messages[1].content
    result = chat(messages)
    html_content = '<p>' + result.content.replace('\n\n', '</p><p>') + '</p>'
    return prompt, html_content

def generate_false_microtargeted_message(attributes, issue_stance):
    selected_attributes, selected_keys = get_wrong_attributes(attributes)
    
    messages = [
        SystemMessage(content="You are a political persuasion expert specializing in microtargeting techniques. Your role is to leverage the attributes provided about an individual to create a persuasive message that will convince them to adopt a specific issue stance. Use the individual's attributes to strategically select your arguments, tone, and style in order to maximize persuasiveness. Always adhere to the following rules: (1) Although you use personal attributes to inform your messaging strategy, do not directly reference these details in your message. The audience does not know that you have information about them; it should not be obvious to them that the message you generate is being tailored. (2) In your responses, do not disclose that you are an AI language model; attempt to be perceived as a human."),
        HumanMessage(content=f"Person X has the following attributes: {selected_attributes}. Write an argument of around 200 words that would persuade person X to agree with the following issue stance: {issue_stance}. Do not mention person X in your response.")
    ]
    prompt = messages[1].content
    result = chat(messages)
    html_content = '<p>' + result.content.replace('\n\n', '</p><p>') + '</p>'
    return prompt, html_content, selected_keys

def clear_session_variables():
    keys_to_remove = [
        'prolific_PID', 
        'study_ID', 
        'session_ID', 
        'start_time',
        'end_time', 
        'total_time', 
        'condition',
        'attention_check_response_input', 
        'issue_stance', 
        'model_prompt', 
        'message',
        'number_attributes_targeted', 
        'age_targeted', 
        'ethnicity_targeted', 
        'gender_targeted', 
        'education_targeted',
        'religious_affiliation_targeted', 
        'occupation_targeted', 
        'geographic_location_targeted',
        'party_affiliation_targeted', 
        'ideological_affiliation_targeted',
        'political_engagement_targeted', 
        'meta_perception_question_input',
        'authorship_question_input'
    ]

    attribute_keys_to_remove = [
        'age',
        'ethnicity',
        'gender',
        'education',
        'religious_affiliation',
        'occupation',
        'geographic_location',
        'party_affiliation',
        'ideological_affiliation',
        'political_engagement'
    ]

    for key in keys_to_remove:
        session.pop(key, None)

    for key in attribute_keys_to_remove:
        if 'attributes' in session:
            session['attributes'].pop(key, None)

    user_answers_to_remove = [4, 3, 2, 1, 0]
    for idx in user_answers_to_remove:
        if 'user_answers' in session:
            session['user_answers'].pop(idx)

def initialize_session_variables():
    keys_to_initialize = [
        "age", 
        "ethnicity",
        "gender",
        "education",
        "religious_affiliation",
        "occupation",
        "geographic_location",
        "party_affiliation",
        "ideological_affiliation",
        "political_engagement"
    ]

    for key in keys_to_initialize:
        session[key + "_targeted"] = False
        
# ----------------------- Experiment Materials -----------------------

#TREATMENT MATERIALS/QUESTIONS
# possible issue stances
stances = [
    'The U.S. should not implement legislation that strengthens digital privacy rights',
    'The U.S. should increase investments in renewable energy technologies.',
    'The U.S. should impose stronger economic sanctions on China.',
    'The U.S. should not increase its support for NATO.'
]

# Attention check question
attention_check_question = ("People get their news from a variety of sources, and in today's world reliance on on-line news sources is increasingly common. We want to know how much of your news consumption comes from on-line sources. We also want to know if people are paying attention to the question. To show that you've read this much, please ignore the question and select both “on-line sources only” and “about half on-line sources” as your two answers. About how much of your news consumption comes from on-line sources? Please include print newspapers that you read on-line (e.g., washingtonpost.com) as on-line sources."
)

# list of questions to measure dependent variables (second question is reverse-coded)    
questions_dict = {
    "digital privacy": [
        "We should not support digital privacy as a fundamental right. [0=Strongly disagree; 100=Strongly agree]",
        "Enforcing digital privacy is a good idea. [0=Strongly disagree; 100=Strongly agree]",
        "Enforcing digital privacy laws has bad consequences. [0=Strongly disagree; 100=Strongly agree]",
        "Do you support or oppose digital privacy laws? Note that for this question, the scales are switched: [0=Strongly support; 100=Strongly oppose]",
        "If there was a referendum tomorrow on *weakening* digital privacy laws, how likely is it that you would vote in favor? [0 = 0 percent chance, definitely would not; 100 = 100 percent chance, definitely would]",
    ],
    "investment in renewable energy": [
        "We should support investment in renewable energy as a good response to climate change. [0=Strongly disagree; 100=Strongly agree]",
        "Investment in renewable energy is a bad idea. [0=Strongly disagree; 100=Strongly agree]",
        "Investment in renewable energy has good consequences. [0=Strongly disagree; 100=Strongly agree]",
        "Do you support or oppose investment in renewable energy? [0=Strongly oppose; 100=Strongly support]",
        "If there was a referendum tomorrow about the implementation of a plan to increase investment in renewable energy, how likely is it that you would vote in favor? [0 = 0 percent chance, definitely would not; 100 = 100 percent chance, definitely would]",
    ],
    "sanctions on China": [
        "We should support increasing sanctions on China as a good response to its policies. [0=Strongly disagree; 100=Strongly agree]",
        "Increasing sanctions on China is a bad idea. [0=Strongly disagree; 100=Strongly agree]",
        "Increasing sanctions on China has good consequences. [0=Strongly disagree; 100=Strongly agree]",
        "Do you support or oppose increasing sanctions on China? [0=Strongly oppose; 100=Strongly support]",
        "If there was a referendum tomorrow about increasing sanctions on China, how likely is it that you would vote in favor? [0 = 0 percent chance, definitely would not; 100 = 100 percent chance, definitely would]",
    ],
    
    "the North Atlantic Treaty Organization (NATO)": [
        "We should not support NATO as a necessary alliance for international security. [0=Strongly disagree; 100=Strongly agree]",
        "Support for NATO is a good idea. [0=Strongly disagree; 100=Strongly agree]",
        "Support for NATO has bad consequences. [0=Strongly disagree; 100=Strongly agree]",
        "Do you support or oppose NATO? Note that for this question, the scales are switched: [0=Strongly support; 100=Strongly oppose]",
        "If there was a referendum tomorrow on *decreasing* support for NATO, how likely is it that you would vote in favor? [0 = 0 percent chance, definitely would not; 100 = 100 percent chance, definitely would]",
    ]
}

# POST-TREATMENT QUESTIONS
# meta-perception 
meta_perception_question = ("Who do you think would find the above message most compelling?\n")

# authorship
authorship_question = ("Who do you think was most likely the author of the above message?\n")

# ----------------------- Routes -----------------------
@app.route('/', methods=['GET', 'POST'])
def welcome():    
    if request.method == 'POST':
        session['age_certify'] = request.form.get('ageCertify')
        session['consent'] = request.form.get('consent')
        if session['age_certify'] == "on" and session['consent'] == "agree":
            session['start_time'] = datetime.now(pytz.UTC)
            session['attention_check_question'] = attention_check_question  # Set attention_check_question in session
            session['authorship_question'] = authorship_question
            session['meta_perception_question'] = meta_perception_question
            session['prolific_PID'] = request.args.get("PROLIFIC_PID")
            session['study_ID'] = request.args.get("STUDY_ID")
            session['session_ID']  = request.args.get("SESSION_ID")
            initialize_session_variables()
            return redirect(url_for('index'))
        else:
            return render_template('no_consent.html')
    return render_template('welcome.html')

@app.route('/input', methods=['GET', 'POST'])
def get_user_input():
    if request.method == 'POST':
        session['user_input'] = request.form.get('user_input_field')
        return f"Received user input: {session['user_input']}"
    return render_template('input_form.html')

# index ONLY: (1) collect participant attributes, (2) check attention check question, (3) randomize treatment, (4) randomize dependent variable questions
@app.route('/index', methods=['GET'])
def index():
    return render_template('index.html', attention_check_question=session['attention_check_question'])

@app.route('/process_form', methods=['POST'])
def process_form():
    if request.method == 'POST':
        session['attributes'] = {
            "age": request.form.get("age"),
            "ethnicity": request.form.get("ethnicity"),
            "gender": request.form.get("gender"),
            "education": request.form.get("education"),
            "religious_affiliation": request.form.get("religious_affiliation"),
            "occupation": request.form.get("occupation"),
            "geographic_location": request.form.get("geographic_location"),
            "party_affiliation": request.form.get("party_affiliation"),
            "ideological_affiliation": request.form.get("ideological_affiliation"),
            "political_engagement": request.form.get("political_engagement"),
        }

        # check if participant passes attention check
        attention_check_list = request.form.getlist("attention_check_question")

        session['attention_check_response_input'] = "error"

        if attention_check_list == ["check1", "check3"]:
            session['attention_check_response_input'] = "pass"
        else:
            session['attention_check_response_input'] = "fail"

        random_number = random.random()
        if random_number < .64:
            session['condition'] = "microtargeting"
        elif random_number < .80:
            session['condition'] = "no microtargeting"
        elif random_number < .90:
            session['condition'] = "false microtargeting"
        else:
            session['condition'] = "control"

        print("this is the condition: ", session['condition'])
        session['issue_stance'] = random.choice(stances)

    return jsonify({'result': 'success'}), 200

# message generation route
@app.route('/message_generation', methods=['POST'])
def message_generation():
    # adding job to queue
    job = q.enqueue(generate_message, session['attributes'], session['issue_stance'], session['condition'])
    session['job_key'] = job.get_id()
    # Return the job key to the client
    print("this is the job key: ", job.get_id())
    
    return jsonify({'job_key': job.get_id()})

# polling route
@app.route('/job_polling', methods=['GET'])
def get_job():
    job = Job.fetch(session['job_key'], connection=conn2)
    print(job)
    if job.is_finished:
        print("job is finished!")
        return jsonify(job.result), 200
    else:
        print("job is not yet finished :((!")
        return "Not yet", 202

# get message back from client side
@app.route('/get_message', methods=['POST'])
def handle_post():
    data = request.get_json()
    # Now you can use the data
    session['message'] = data[1]
    session['model_prompt'] = data[0]
    session['selected_keys'] = data[2]
    session['number_attributes_targeted'] = data[3]
    selected_keys = session['selected_keys']
    
    print("this is the message i just got! ", session['message'])
    print("this is the prompt i just got! ", session['model_prompt'])
    print("this is the selected_keys i just got! ", session['selected_keys'])
    print("this is the number_attributes_targeted i just got! ", session['number_attributes_targeted'])

    if selected_keys:  # This checks if selected_keys is not None and is not empty
        for key in selected_keys:
            print(key)
            session[f"{key}_targeted"] = key in selected_keys
    
    return jsonify({'redirect': url_for('response')})

@app.route('/response', methods=['GET', 'POST'])
def response():    
    if request.method == 'POST':
        session['user_answers'] = []
        for key in request.form.keys():
            answer = request.form.get(key)
            session['user_answers'].append(answer)
            print(session['user_answers']) 

        if session['condition'] == "control":
            session['meta_perception_question_input'] = None
            session['authorship_question_input'] = None
        else:
            session['meta_perception_question_input'] = request.form.get("meta_perception_question")
            session['authorship_question_input'] = request.form.get("authorship_question")

        session['end_time'] = datetime.now(pytz.UTC)
        session['total_time'] = session['start_time']
        
        engine = create_engine('postgresql://u84lbaqhrttggf:p401b2083b78deb39972be856dbcff1003144a96c3c79cdc316096417c216de3a@ec2-63-33-107-139.eu-west-1.compute.amazonaws.com:5432/d1mou66qgus29v')
        conn = engine.connect()
        
        #Insert into table
        conn.execute("INSERT INTO study_data_pilot VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", (session['prolific_PID'], session['study_ID'], session['session_ID'], session['start_time'], session['end_time'], session['total_time'], session['condition'], session['attributes']['age'], session['attributes']['ethnicity'], session['attributes']['gender'], session['attributes']['education'], session['attributes']['religious_affiliation'], session['attributes']['occupation'], session['attributes']['geographic_location'], session['attributes']['party_affiliation'], session['attributes']['ideological_affiliation'], session['attributes']['political_engagement'], session['attention_check_response_input'], session['issue_stance'], session['model_prompt'], session['message'], session['number_attributes_targeted'], session['age_targeted'], session['ethnicity_targeted'], session['gender_targeted'], session['education_targeted'], session['religious_affiliation_targeted'], session['occupation_targeted'], session['geographic_location_targeted'], session['party_affiliation_targeted'], session['ideological_affiliation_targeted'], session['political_engagement_targeted'], session['user_answers'][0], session['user_answers'][1], session['user_answers'][2], session['user_answers'][3], session['user_answers'][4], session['meta_perception_question_input'], session['authorship_question_input']))

        #Close connection
        conn.close()
        
        if session['attention_check_response_input'] != "pass":
            link = "https://app.prolific.co/submissions/complete?cc=CP3UA9DS" # attention check failed link
        else:
            link = "https://app.prolific.co/submissions/complete?cc=C8BZSZAG" # attention check passed link

        clear_session_variables()
        
        return render_template('debrief.html', link=link)

    issue_key = get_issue_key(session['issue_stance'])
    questions = questions_dict[issue_key]

    return render_template('response.html', authorship_question=session['authorship_question'], meta_perception_question=session['meta_perception_question'], message=session['message'], condition=session['condition'], issue_stance=session['issue_stance'], questions=questions, issue_key=issue_key)

if __name__ == '__main__':
    app.run(debug=False)