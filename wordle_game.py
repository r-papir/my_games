from colorama import Back
import random

def print_green(letter):
    print(Back.GREEN + f" {letter} " + Back.RESET, end='')

def print_yellow(letter):
    print(Back.YELLOW + f" {letter} " + Back.RESET, end='')

def print_gray(letter):
    print(Back.LIGHTBLACK_EX + f" {letter} " + Back.RESET, end='')

class WordleGame:

    def __init__(self):
        self.guess_memory = []
        self.max_guesses = 6
        self.is_won = False
        self.answer = None  # will come from WordList later

    def instructions(self):
        print(" ")
        print("INSTRUCTIONS:")
        print(" ")
        print("Players are given 6 tries to guess a valid 5-letter word (excluding plural nouns).")
        print("The color of a tile will change to show you how close your guess was.")
        print("If the tile turns green, the letter is in the word AND it is in the correct spot.")
        print("If the tile turns yellow, the letter is in the word, but it is NOT in the correct spot.")
        print("If the tile turns gray, the letter is NOT in the word at all.")
        print("Would you like to play? (Yes/No)")
        
        if input().lower() == "yes":
            self.play()
        else:
            print("Goodbye.")
        

    def play(self):

        guess_counter = 0

        while guess_counter < self.max_guesses and not self.is_won:

            guess = input("Please enter a 5-letter word: ")

            if not self.word_list.is_valid(guess):
                print("Oh no! Invalid word.")
                continue

            current_guess = Guesses(guess)
            current_guess.check_letter(self.answer)
            guess_counter += 1

            if guess == self.answer:
                self.is_won = True
                print("\nYou won!")
            else:
                print(f"\nAttempts remaining: {self.max_guesses - guess_counter}")
        
        if not self.is_won:
            print(f"\nYou lost! The word was: {self.answer}")


class Guesses:

    def __init__(self, word):
        self.word = word
    
    def check_letter(self, answer):        
        for i in range(5):
            if self.word[i] == answer[i]:
                print_green(self.word[i])
            elif self.word[i] in answer:
                print_yellow(self.word[i])
            else:
                print_gray(self.word[i])


class WordList:
    def __init__(self, filename):
        with open(filename) as f:
            self.words = [line.strip() for line in f]

    def pick_random(self):
        return random.choice(self.words)

    def is_valid(self, word):
        return len(word) == 5 and word in self.words

if __name__ == "__main__":
    word_list = WordList("wordle.txt")
    game = WordleGame()
    game.answer = word_list.pick_random()
    game.word_list = word_list
    game.instructions()