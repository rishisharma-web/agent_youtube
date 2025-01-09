import json
import pyttsx3
import speech_recognition as sr
import time
import difflib
import vlc
import yt_dlp
import threading
from langchain.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
class YouTubeQuizAgent:
    def __init__(self, youtube_url, GEMINI_API_KEY):
        # Initialize text-to-speech engine
        self.engine = pyttsx3.init()
        # Initialize speech recognizer
        self.recognizer = sr.Recognizer()
        self.questions_data = None
        self.model=ChatGoogleGenerativeAI(model='gemini-1.5-pro', temperature=0.3, google_api_key=GEMINI_API_KEY)
        # Initialize video player with YouTube URL
        self.setup_video_player(youtube_url)
    
    def get_video_url(self, youtube_url):
        """Get direct video URL from YouTube URL"""
        ydl_opts = {
            'format': 'best[height<=720]',  # Limit quality to 720p
            'quiet': True,
            'no_warnings': True
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
                return info['url']
        except Exception as e:
            print(f"Error getting video URL: {e}")
            return None
        
    def setup_video_player(self, youtube_url):
        """Setup video player for YouTube video"""
        # Get direct video URL
        stream_url = self.get_video_url(youtube_url)
        if not stream_url:
            raise Exception("Could not get video stream URL")

        # Setup VLC player
        self.instance = vlc.Instance('--verbose 0')
        self.player = self.instance.media_player_new()
        self.media = self.instance.media_new(stream_url)
        self.player.set_media(self.media)

        # Set up a simple window for the video
        self.player.set_hwnd(0)  # This will create a new window for the video
        
    def load_questions(self, json_data):
        """Load questions from JSON data"""
        self.questions_data = json_data["questions"]
        
    def speak(self, text):
        """Convert text to speech"""
        self.engine.say(text)
        self.engine.runAndWait()
        
    def listen(self):
        """Listen for user input and convert speech to text"""
        with sr.Microphone() as source:
            print("Listening...")
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = self.recognizer.listen(source)
            try:
                return self.recognizer.recognize_google(audio)
            except sr.UnknownValueError:
                return None
            except sr.RequestError:
                print("Could not request results from speech recognition service")
                return None

    def pause_video(self):
        """Pause the YouTube video"""
        self.player.pause()
        
    def play_video(self):
        """Play the YouTube video"""
        self.player.play()
        
    def set_video_time(self, timestamp):
        """Set video time to specific timestamp in seconds"""
        self.player.set_time(int(float(timestamp) * 1000))

    def get_current_time(self):
        """Get current video time in seconds"""
        return self.player.get_time() / 1000

        
    def handle_mcq_question(self, question_data):
        """Handle multiple choice questions"""
        # Read the question
        self.speak(question_data["question"]["question_description"])
        time.sleep(1)
        
        # Read options
        for option in question_data["question"]["options"]:
            option_text = f"Option {option['option_id']}: {option['option_description']}"
            self.speak(option_text)
            time.sleep(0.5)
            
        # Get answer
        # self.speak("Please say your answer as option A, B, C, or D")
        # while True:
        #     answer = self.listen()
        #     if answer:
        #         answer = answer.upper()
        #         answer = ''.join(char for char in answer if char in 'ABCD')
        #         if answer in ['A', 'B', 'C', 'D']:
        #             return answer == question_data["answer"]
        #     self.speak("Please say a valid option: A, B, C, or D")
        answers = []
        self.speak("Please provide your answer. Say 'finished' when you're done.")
        # Collect all parts of the answer until user says "finished"
        while True:
            response = self.listen()
            if not response:
                continue
                
            response = response.strip().lower()
            if response == "finished":
                if not answers:  # If no answer was provided before saying finished
                    self.speak("Please provide an answer before finishing.")
                    continue
                break
                
            answers.append(response)
            # self.speak("Continue with your answer or say 'finished' when done.")
        
        # Combine all parts of the answer
        full_answer = " ".join(answers)
        print(full_answer)
        # question_dat=question_data["question"]
        # Construct prompt for LLM
        # prompt = f""" Question, options and correct answer is present in the json format
        # json: {question_dat}
        
        # User's answer: {full_answer}
        
        # Compare the user's answer with the correct answer. Consider the intent and meaning, not just exact wording.
        # Respond with 'True' if the user's answer demonstrates correct understanding, or 'False' if it does not.
        # OUTPUT: True/False
        # """
        messages=[("system", "You are specialized in comparing two answers and determining if they are correct or not. Please compare the user's answer with the correct answer and provide a response of 'True' if the user's answer demonstrates correct understanding, or 'False' if it does not."),
                  ("user", """ Question, options and correct answer is present in the json format
        json: {question_data}
        
        User's answer: {full_answer}
        
        Compare the user's answer with the correct answer. Consider the intent and meaning, not just exact wording. User can also provide answer in options like Option A, Option B, Option C, and Option D. So, check is it the correct answer or not.
        Respond with 'True' if the user's answer demonstrates correct understanding, or 'False' if it does not.
        OUTPUT: True/False (Strictly)
        """)]
        try:
            # Call your LLM service here
            prompt_template = ChatPromptTemplate.from_messages(messages)
            prompt = prompt_template.invoke({"question_data":question_data, "full_answer":full_answer})
            result = self.model.invoke(prompt)
            print(result.content)
            # Parse LLM response - assuming it starts with true/false
            
            return result.content.strip().lower() == "true"
            
        except Exception as e:
            self.speak("Sorry, I couldn't validate your answer. Please try again.")
            print(f"LLM validation error: {str(e)}")
            return False

    def handle_fill_ups_question(self, question_data):
        """Handle fill in the blanks questions"""
        self.speak(question_data["question"].replace("_____", "blank"))
        self.speak("Please provide your answer. Say 'finished' when you're done.")
        answers = []
        while True:
            response = self.listen()
            if not response:
                continue
                
            # response = response.strip().lower()
            if response == "finished":
                if not answers:  # If no answer was provided before saying finished
                    self.speak("Please provide an answer before finishing.")
                    continue
                break
                
            answers.append(response)
            # self.speak("Continue with your answer or say 'finished' when done.")
        
        # Combine all parts of the answer
        full_answer = " ".join(answers)
        print(full_answer)
        question_dat=question_data["answer"]
        messages=[("system", "You are specialized in comparing two answers and determining if they are correct or not. Please compare the user's answer with the correct answer and provide a response of 'True' if the user's answer demonstrates correct understanding, or 'False' if it does not."),
                  ("user", """ Given below are the correct answer and user's answer. 
        correct answer: {question_dat}
        
        User's answer: {full_answer}
        
        Compare the user's answer with the correct answer. Consider the intent and meaning, not just exact wording.
        Respond with 'True' if the user's answer demonstrates correct understanding, or 'False' if it does not.
        OUTPUT: True/False
        """)]
        try:
            # Call your LLM service here
            prompt_template = ChatPromptTemplate.from_messages(messages)
            prompt = prompt_template.invoke({"question_dat":question_dat, "full_answer":full_answer})
            result = self.model.invoke(prompt)
            print(result.content)
            # Parse LLM response - assuming it starts with true/false
            
            return result.content.strip().lower() == "true"
            
        except Exception as e:
            self.speak("Sorry, I couldn't validate your answer. Please try again.")
            print(f"LLM validation error: {str(e)}")
            return False

    def handle_one_word_question(self, question_data):
        """Handle one word answer questions"""
        self.speak(question_data["question"])
        self.speak("please answer in one word only")
        
        while True:
            answer = self.listen()
            print(answer)
            if answer:
                similarity = difflib.SequenceMatcher(None, 
                    answer.lower(), 
                    question_data["answer"].lower()
                ).ratio()
                return similarity > 0.8
            self.speak("That's wrong man.")

    def handle_subjective_question(self, question_data):
        """Handle subjective questions"""
        self.speak(question_data["question"])
        self.speak("Please provide your detailed answer")
        
        full_answer = self.listen()
    
        print(full_answer)
        question_dat=question_data["answer"]
        messages=[("system", "You are specialized in comparing two answers and determining if they are correct or not. Please compare the user's answer with the correct answer and provide a response of 'True' if the user's answer demonstrates correct understanding, or 'False' if it does not."),
                  ("user", """ Given below are the correct answer and user's answer. 
        correct answer: {question_dat}
        
        User's answer: {full_answer}
        
        Compare the user's answer with the correct answer. Consider the intent and meaning, not just exact wording.
        Respond with 'True' if the user's answer demonstrates correct understanding, or 'False' if it does not.
        OUTPUT: True/False
        """)]
        try:
            # Call your LLM service here
            prompt_template = ChatPromptTemplate.from_messages(messages)
            prompt = prompt_template.invoke({"question_dat":question_dat, "full_answer":full_answer})
            result = self.model.invoke(prompt)
            print(result.content)
            # Parse LLM response - assuming it starts with true/false
            
            return result.content.strip().lower() == "true"
            
        except Exception as e:
            self.speak("Sorry, I couldn't validate your answer. Please try again.")
            print(f"LLM validation error: {str(e)}")
            return False

    def provide_feedback(self, is_correct, question_data):
        """Provide feedback based on the answer"""
        if question_data["question_type"] == "mcq":
                for option in question_data["question"]["options"]:
                    if option["option_id"] == question_data["answer"]:
                        answer_option = option["option_description"]
        if is_correct:
            self.speak("That's correct! ")
            if question_data["question_type"] == "mcq":
               self.speak(f"The answer is: {answer_option}")
            else:
                self.speak(f"The answer is: {question_data['answer']}")
        else:
            self.speak("That's not quite right. ")
            if question_data["question_type"] == "mcq":
                self.speak(f"The correct answer is: {answer_option}")
            else:
                self.speak(f"The correct answer is: {question_data['answer']}")

    def handle_question(self, question_data):
        """Handle a question based on its type"""
        # Pause video at timestamp
        self.set_video_time(float(question_data['timestamp']))
        self.pause_video()
        
        question_type = question_data["question_type"]
        handlers = {
            "mcq": self.handle_mcq_question,
            "fill_ups": self.handle_fill_ups_question,
            "one_word": self.handle_one_word_question,
            "subjective": self.handle_subjective_question
        }
        
        if question_type in handlers:
            is_correct = handlers[question_type](question_data)
            self.provide_feedback(is_correct, question_data)
            self.play_video()  # Resume video after question
            return is_correct
        else:
            print(f"Unsupported question type: {question_type}")
            return False

    def run_video_quiz(self):
        """Run the complete video quiz"""
        if not self.questions_data:
            self.speak("No questions loaded")
            return
            
        self.speak("Starting the video quiz. The video will pause automatically for questions.")
        self.play_video()
        
        correct_answers = 0
        total_questions = len(self.questions_data)
        
        # Sort questions by timestamp
        sorted_questions = sorted(self.questions_data, 
                                key=lambda x: float(x['timestamp']))
        
        for question in sorted_questions:
            # Wait until we reach the question timestamp
            current_time = self.get_current_time()
            question_time = float(question['timestamp'])
            
            while current_time < question_time:
                time.sleep(0.1)
                current_time = self.get_current_time()
                if current_time < 0:  # Video hasn't started playing yet
                    continue
            
            if self.handle_question(question):
                correct_answers += 1
                
        # Final score
        self.speak(f"Quiz completed! You got {correct_answers} out of {total_questions} questions correct.")


def main():
    # YouTube video URL - replace with your video URL
    youtube_url = "https://www.youtube.com/watch?v=oKvscIVhelo"

    with open('config.json', 'r') as file:
        config = json.load(file)
        GEMINI_API_KEY = config["GEMINI_API_KEY"]
    
    try:
        # Load questions from JSON file
        with open('questions.json', 'r') as file:
            questions_data = json.load(file)
        
        # Create and run the quiz agent
        agent = YouTubeQuizAgent(youtube_url, GEMINI_API_KEY)
        agent.load_questions(questions_data)
        agent.run_video_quiz()
        
    except Exception as e:
        print(f"An error occurred: {e}")
        print("Please make sure you have:")
        print("1. A valid YouTube URL")
        print("2. VLC media player installed")
        print("3. Valid questions.json file")
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()