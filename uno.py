import random
import time
import os
import json
import requests
from enum import Enum
from typing import List, Optional, Tuple, Dict

class Colors:
    RED = '\033[91m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

class Color(Enum):
    RED = "Red"
    BLUE = "Blue"
    GREEN = "Green"
    YELLOW = "Yellow"
    WILD = "Wild"

class CardType(Enum):
    NUMBER = "Number"
    SKIP = "Skip"
    REVERSE = "Reverse"
    DRAW_TWO = "Draw Two"
    WILD = "Wild"
    WILD_DRAW_FOUR = "Wild Draw Four"

class Difficulty(Enum):
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"

class Card:
    def __init__(self, color: Color, card_type: CardType, value: Optional[int] = None):
        self.color = color
        self.card_type = card_type
        self.value = value
    
    def __str__(self):
        color_code = self._get_color_code()
        
        if self.card_type == CardType.NUMBER:
            card_text = f"{self.color.value} {self.value}"
        elif self.card_type in [CardType.WILD, CardType.WILD_DRAW_FOUR]:
            card_text = f"{self.card_type.value}"
        else:
            card_text = f"{self.color.value} {self.card_type.value}"
        
        return f"{color_code}{Colors.BOLD}{card_text}{Colors.END}"
    
    def _get_color_code(self):
        color_map = {
            Color.RED: Colors.RED,
            Color.BLUE: Colors.BLUE,
            Color.GREEN: Colors.GREEN,
            Color.YELLOW: Colors.YELLOW,
            Color.WILD: Colors.PURPLE
        }
        return color_map.get(self.color, Colors.WHITE)
    
    def can_play_on(self, other_card: 'Card', current_color: Color) -> bool:
        if self.card_type in [CardType.WILD, CardType.WILD_DRAW_FOUR]:
            return True
        if self.color == current_color:
            return True
        if other_card.card_type == CardType.NUMBER and self.card_type == CardType.NUMBER:
            return self.value == other_card.value
        return self.card_type == other_card.card_type
    
    def to_dict(self):
        return {
            "color": self.color.value,
            "type": self.card_type.value,
            "value": self.value
        }

class GeminiAI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        
    def get_card_choice(self, game_state: Dict) -> Dict:
        try:
            prompt = self._create_game_prompt(game_state)
            
            headers = {
                "Content-Type": "application/json"
            }
            
            payload = {
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 200
                }
            }
            
            response = requests.post(
                f"{self.base_url}?key={self.api_key}",
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['candidates'][0]['content']['parts'][0]['text']
                return self._parse_ai_response(content)
            else:
                print(f"API Error: {response.status_code}")
                return self._fallback_choice(game_state)
                
        except Exception as e:
            print(f"Gemini AI Error: {e}")
            return self._fallback_choice(game_state)
    
    def _create_game_prompt(self, game_state: Dict) -> str:
        prompt = f"""
You are playing UNO as an expert AI player. Analyze the game state and choose the best card to play.

GAME STATE:
- Current top card: {game_state['top_card']}
- Current color: {game_state['current_color']}
- Your hand: {game_state['my_hand']}
- Playable cards: {game_state['playable_cards']}
- Opponent hand size: {game_state['opponent_hand_size']}
- My hand size: {game_state['my_hand_size']}
- Cards left in deck: {game_state['deck_size']}

STRATEGY PRIORITIES:
1. If opponent has 1 card (UNO), prioritize aggressive cards (Wild Draw Four, Draw Two, Skip)
2. If you have few cards, play conservatively to win
3. If you have many cards, get rid of high-value cards first
4. Consider color strategy for Wild cards

PLAYABLE CARDS (choose from these):
{json.dumps(game_state['playable_cards'], indent=2)}

Respond with ONLY a JSON object in this exact format:
{{
    "card_index": <index of chosen card from playable_cards list (0-based)>,
    "reasoning": "<brief explanation>",
    "wild_color": "<Red/Blue/Green/Yellow - only if playing Wild card, otherwise null>"
}}

Example response:
{{"card_index": 0, "reasoning": "Playing Draw Two to prevent opponent from winning", "wild_color": null}}
"""
        return prompt
    
    def _parse_ai_response(self, content: str) -> Dict:
        try:
            content = content.strip()
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
            
            response_data = json.loads(content)
            
            if 'card_index' in response_data:
                return {
                    'card_index': response_data['card_index'],
                    'reasoning': response_data.get('reasoning', 'AI strategic choice'),
                    'wild_color': response_data.get('wild_color')
                }
            else:
                raise ValueError("Invalid response format")
                
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            print(f"Failed to parse AI response: {e}")
            print(f"Raw response: {content}")
            return {'card_index': 0, 'reasoning': 'Fallback choice', 'wild_color': None}
    
    def _fallback_choice(self, game_state: Dict) -> Dict:
        playable_cards = game_state['playable_cards']
        
        opponent_cards = game_state.get('opponent_hand_size', 7)
        
        if opponent_cards == 1:
            for i, card in enumerate(playable_cards):
                if card['type'] in ['Wild Draw Four', 'Draw Two', 'Skip']:
                    return {'card_index': i, 'reasoning': 'Aggressive play (fallback)', 'wild_color': 'Red'}
        
        return {'card_index': 0, 'reasoning': 'Safe choice (fallback)', 'wild_color': 'Red'}

class AIStrategy:
    def __init__(self, difficulty: Difficulty, gemini_ai: Optional[GeminiAI] = None):
        self.difficulty = difficulty
        self.gemini_ai = gemini_ai
        self.name = f"Computer ({difficulty.value})"
    
    def choose_card(self, playable_cards: List[Card], game_state: Dict) -> Tuple[Card, Optional[str]]:
        if self.difficulty == Difficulty.HARD and self.gemini_ai:
            return self._hard_ai_choice(playable_cards, game_state)
        elif self.difficulty == Difficulty.MEDIUM:
            return self._medium_ai_choice(playable_cards, game_state)
        else:
            return self._easy_ai_choice(playable_cards, game_state)
    
    def _hard_ai_choice(self, playable_cards: List[Card], game_state: Dict) -> Tuple[Card, Optional[str]]:
        api_game_state = {
            'top_card': game_state['top_card'].to_dict(),
            'current_color': game_state['current_color'].value,
            'my_hand': [card.to_dict() for card in game_state.get('my_hand', [])],
            'playable_cards': [card.to_dict() for card in playable_cards],
            'opponent_hand_size': game_state.get('opponent_hand_size', 7),
            'my_hand_size': game_state.get('my_hand_size', 7),
            'deck_size': game_state.get('deck_size', 50)
        }
        
        ai_decision = self.gemini_ai.get_card_choice(api_game_state)
        
        card_index = ai_decision.get('card_index', 0)
        if 0 <= card_index < len(playable_cards):
            chosen_card = playable_cards[card_index]
            reasoning = ai_decision.get('reasoning', 'AI strategic choice')
            wild_color = ai_decision.get('wild_color')
            
            return chosen_card, wild_color, reasoning
        
        return playable_cards[0], None, "Fallback choice"
    
    def _medium_ai_choice(self, playable_cards: List[Card], game_state: Dict) -> Tuple[Card, Optional[str]]:
        opponent_cards = game_state.get('opponent_hand_size', 7)
        my_hand_size = game_state.get('my_hand_size', 7)
        
        if opponent_cards == 1:
            aggressive_cards = [c for c in playable_cards 
                              if c.card_type in [CardType.WILD_DRAW_FOUR, 
                                               CardType.DRAW_TWO,
                                               CardType.SKIP]]
            if aggressive_cards:
                return aggressive_cards[0], None, "Preventing opponent victory"
        
        priority_order = [
            CardType.WILD_DRAW_FOUR,
            CardType.DRAW_TWO,
            CardType.SKIP,
            CardType.REVERSE,
            CardType.WILD
        ]
        
        for card_type in priority_order:
            matching_cards = [c for c in playable_cards if c.card_type == card_type]
            if matching_cards:
                return matching_cards[0], None, f"Playing {card_type.value}"
        
        number_cards = [c for c in playable_cards if c.card_type == CardType.NUMBER]
        if number_cards:
            chosen = max(number_cards, key=lambda x: x.value)
            return chosen, None, "Playing high-value number card"
        
        return playable_cards[0], None, "Basic choice"
    
    def _easy_ai_choice(self, playable_cards: List[Card], game_state: Dict) -> Tuple[Card, Optional[str]]:
        if random.random() < 0.3 and len(playable_cards) > 1:
            non_action_cards = [c for c in playable_cards 
                              if c.card_type not in [CardType.WILD_DRAW_FOUR, 
                                                   CardType.DRAW_TWO, 
                                                   CardType.SKIP]]
            if non_action_cards:
                return random.choice(non_action_cards), None, "Random choice"
        
        return random.choice(playable_cards), None, "Random play"
    
    def choose_wild_color(self, hand: List[Card], wild_color_hint: Optional[str] = None) -> Color:
        if wild_color_hint:
            color_map = {
                'Red': Color.RED, 'Blue': Color.BLUE, 
                'Green': Color.GREEN, 'Yellow': Color.YELLOW
            }
            return color_map.get(wild_color_hint, Color.RED)
        
        color_counts = {Color.RED: 0, Color.BLUE: 0, Color.GREEN: 0, Color.YELLOW: 0}
        for card in hand:
            if card.color in color_counts:
                color_counts[card.color] += 1
        
        return max(color_counts, key=color_counts.get)

class Deck:
    def __init__(self):
        self.cards = []
        self._create_deck()
        self.shuffle()
    
    def _create_deck(self):
        colors = [Color.RED, Color.BLUE, Color.GREEN, Color.YELLOW]
        
        for color in colors:
            self.cards.append(Card(color, CardType.NUMBER, 0))
            for num in range(1, 10):
                self.cards.append(Card(color, CardType.NUMBER, num))
                self.cards.append(Card(color, CardType.NUMBER, num))
        
        for color in colors:
            for _ in range(2):
                self.cards.append(Card(color, CardType.SKIP))
                self.cards.append(Card(color, CardType.REVERSE))
                self.cards.append(Card(color, CardType.DRAW_TWO))
        
        for _ in range(4):
            self.cards.append(Card(Color.WILD, CardType.WILD))
            self.cards.append(Card(Color.WILD, CardType.WILD_DRAW_FOUR))
    
    def shuffle(self):
        random.shuffle(self.cards)
    
    def draw_card(self) -> Optional[Card]:
        return self.cards.pop() if self.cards else None
    
    def add_card(self, card: Card):
        self.cards.insert(0, card)
    
    def is_empty(self) -> bool:
        return len(self.cards) == 0

class Player:
    def __init__(self, name: str, is_computer: bool = False, ai_strategy: Optional[AIStrategy] = None):
        self.name = name
        self.hand = []
        self.is_computer = is_computer
        self.ai_strategy = ai_strategy
    
    def add_card(self, card: Card):
        self.hand.append(card)
    
    def remove_card(self, card: Card):
        if card in self.hand:
            self.hand.remove(card)
    
    def has_playable_card(self, top_card: Card, current_color: Color) -> bool:
        return any(card.can_play_on(top_card, current_color) for card in self.hand)
    
    def get_playable_cards(self, top_card: Card, current_color: Color) -> List[Card]:
        return [card for card in self.hand if card.can_play_on(top_card, current_color)]
    
    def has_won(self) -> bool:
        return len(self.hand) == 0

class UNOGame:
    def __init__(self, gemini_api_key: Optional[str] = None):
        self.deck = Deck()
        self.discard_pile = []
        self.players = []
        self.current_player_index = 0
        self.current_color = None
        self.direction = 1
        self.game_over = False
        self.winner = None
        self.action_log = []
        self.gemini_ai = GeminiAI(gemini_api_key) if gemini_api_key else None
    
    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def log_action(self, message: str):
        self.action_log.append(message)
        if len(self.action_log) > 5:
            self.action_log.pop(0)
    
    def display_welcome_screen(self):
        self.clear_screen()
        print(f"""
{Colors.PURPLE}
                                              
    {Colors.RED}██    ██ {Colors.BLUE}███    ██  {Colors.GREEN}██████{Colors.PURPLE}          
    {Colors.RED}██    ██ {Colors.BLUE}████   ██ {Colors.GREEN}██    ██{Colors.PURPLE}        
    {Colors.RED}██    ██ {Colors.BLUE}██ ██  ██ {Colors.GREEN}██    ██{Colors.PURPLE}        
    {Colors.RED}██    ██ {Colors.BLUE}██  ██ ██ {Colors.GREEN}██    ██{Colors.PURPLE}        
     {Colors.RED}██████  {Colors.BLUE}██   ████  {Colors.GREEN}██████{Colors.PURPLE}         
                                                
{Colors.BOLD}{Colors.WHITE}Cli-Based Card Game Interface{Colors.PURPLE}                                            
{Colors.END}

{Colors.WHITE}Challenge yourself against smart AI opponents
Experience the classic card game with modern AI!{Colors.END}
""")

    def get_player_setup(self):
        print(f"{Colors.YELLOW}🎮 PLAYER SETUP{Colors.END}")
        print(f"{Colors.YELLOW}{'─'*30}{Colors.END}")
        
        while True:
            player_name = input(f"{Colors.CYAN}Enter your name: {Colors.END}").strip()
            if player_name:
                break
            print(f"{Colors.RED}Please enter a valid name!{Colors.END}")
        
        return player_name

    def display_ai_selection(self):
        print(f"\n{Colors.YELLOW}🤖 CHOOSE YOUR OPPONENT{Colors.END}")
        print(f"{Colors.YELLOW}{'─'*40}{Colors.END}")
        
        print(f"""
{Colors.GREEN}┌─ 1. ROOKIE AI ─────────────────────────┐
│  {Colors.WHITE}• Perfect for beginners                 {Colors.GREEN}│
│  {Colors.WHITE}• Random strategic moves                {Colors.GREEN}│
│  {Colors.WHITE}• Easy to beat                          {Colors.GREEN}│
└────────────────────────────────────────┘{Colors.END}

{Colors.YELLOW}┌─ 2. SMART AI ──────────────────────────┐
│  {Colors.WHITE}• Balanced difficulty                   {Colors.YELLOW}│
│  {Colors.WHITE}• Uses basic game strategy              {Colors.YELLOW}│  
│  {Colors.WHITE}• Good for practice                     {Colors.YELLOW}│
└────────────────────────────────────────┘{Colors.END}

{Colors.RED}┌─ 3. GENIUS AI ─────────────────────────┐
│  {Colors.WHITE}• Ultimate challenge                    {Colors.RED}│
│  {Colors.WHITE}• Powered by Google Gemini AI          {Colors.RED}│
│  {Colors.WHITE}• Advanced strategic thinking           {Colors.RED}│""")
        
        if self.gemini_ai:
            print(f"{Colors.GREEN}│  ✓ {Colors.WHITE}UNLOCKED - Ready to play!           {Colors.RED}│")
        else:
            print(f"{Colors.YELLOW}│  🔒 {Colors.WHITE}LOCKED - Requires API key            {Colors.RED}│")
        
        print(f"{Colors.RED}└────────────────────────────────────────┘{Colors.END}")

    def get_ai_selection(self):
        while True:
            try:
                max_choice = 3 if self.gemini_ai else 2
                choice = input(f"\n{Colors.CYAN}Select opponent (1-{max_choice}): {Colors.END}").strip()
                
                if choice == "1":
                    return Difficulty.EASY
                elif choice == "2":
                    return Difficulty.MEDIUM
                elif choice == "3":
                    if self.gemini_ai:
                        return Difficulty.HARD
                    else:
                        print(f"{Colors.RED}❌ Genius AI requires API key! Choose option 1 or 2.{Colors.END}")
                else:
                    print(f"{Colors.RED}❌ Please enter 1, 2, or 3{Colors.END}")
            except:
                print(f"{Colors.RED}❌ Invalid input! Please try again.{Colors.END}")

    def setup_game(self):
        self.display_welcome_screen()
        
        player_name = self.get_player_setup()
        self.display_ai_selection()
        difficulty = self.get_ai_selection()
        
        print(f"\n{Colors.GREEN}✓ Game setup complete!{Colors.END}")
        print(f"{Colors.WHITE}Player: {Colors.BOLD}{player_name}{Colors.END}")
        print(f"{Colors.WHITE}Opponent: {Colors.BOLD}Computer ({difficulty.value}){Colors.END}")
        
        input(f"\n{Colors.CYAN}Press Enter to start the game...{Colors.END}")
        
        ai_strategy = AIStrategy(difficulty, self.gemini_ai)
        
        self.players = [
            Player(player_name, is_computer=False),
            Player(ai_strategy.name, is_computer=True, ai_strategy=ai_strategy)
        ]
        
        for _ in range(7):
            for player in self.players:
                card = self.deck.draw_card()
                if card:
                    player.add_card(card)
        
        while True:
            top_card = self.deck.draw_card()
            if top_card and top_card.card_type not in [CardType.WILD, CardType.WILD_DRAW_FOUR]:
                self.discard_pile.append(top_card)
                self.current_color = top_card.color
                break
        
        self.log_action(f"Game started! Difficulty: {difficulty.value}")
        self.log_action(f"First card: {self.get_top_card()}")
    
    def get_top_card(self) -> Card:
        return self.discard_pile[-1] if self.discard_pile else None
    
    def get_current_player(self) -> Player:
        return self.players[self.current_player_index]
    
    def next_player(self):
        self.current_player_index = (self.current_player_index + self.direction) % len(self.players)
    
    def reverse_direction(self):
        self.direction *= -1
    
    def display_game_state(self):
        self.clear_screen()
        
        print(f"{Colors.CYAN}{Colors.BOLD}🎯 UNO GAME{Colors.END}")
        print(f"{Colors.CYAN}-{Colors.END}" * 50)
        
        top_card = self.get_top_card()
        current_color_display = self._get_color_display(self.current_color)
        print(f"Current Card: {top_card} | Color: {current_color_display}")
        print(f"{Colors.WHITE}Deck: {len(self.deck.cards)} cards{Colors.END}")
        print()
        
        for i, player in enumerate(self.players):
            status = f"{Colors.GREEN}▶ {Colors.END}" if i == self.current_player_index else "  "
            uno_status = f" {Colors.RED}{Colors.BOLD}(UNO!){Colors.END}" if len(player.hand) == 1 else ""
            player_name = f"{Colors.BOLD}{player.name}{Colors.END}" if not player.is_computer else f"{Colors.CYAN}{player.name}{Colors.END}"
            print(f"{status}{player_name}: {len(player.hand)} cards{uno_status}")
        print()
        
        if self.action_log:
            print(f"{Colors.YELLOW}Recent Actions:{Colors.END}")
            for action in self.action_log[-3:]:
                print(f"  {Colors.WHITE}• {action}{Colors.END}")
            print()
        
        if not self.get_current_player().is_computer:
            print(f"{Colors.BOLD}Your Hand:{Colors.END}")
            for i, card in enumerate(self.get_current_player().hand):
                print(f"  {Colors.WHITE}{i + 1}.{Colors.END} {card}")
            print()
    
    def _get_color_display(self, color: Color):
        color_code = {
            Color.RED: Colors.RED,
            Color.BLUE: Colors.BLUE,
            Color.GREEN: Colors.GREEN,
            Color.YELLOW: Colors.YELLOW,
            Color.WILD: Colors.PURPLE
        }.get(color, Colors.WHITE)
        
        return f"{color_code}{Colors.BOLD}{color.value}{Colors.END}"
    
    def human_turn(self, player: Player):
        playable_cards = player.get_playable_cards(self.get_top_card(), self.current_color)
        
        if not playable_cards:
            print("No playable cards. Drawing...")
            new_card = self.deck.draw_card()
            if new_card:
                player.add_card(new_card)
                self.log_action(f"{player.name} drew a card")
                
                if new_card.can_play_on(self.get_top_card(), self.current_color):
                    choice = input(f"Play drawn card ({new_card})? (y/n): ").lower()
                    if choice == 'y':
                        self.play_card(player, new_card)
                        return
            
            self.log_action(f"{player.name}'s turn skipped")
            return
        
        print(f"{Colors.GREEN}Playable Cards:{Colors.END}")
        for i, card in enumerate(playable_cards):
            print(f"  {Colors.WHITE}{i + 1}.{Colors.END} {card}")
        
        while True:
            try:
                choice = input(f"\n{Colors.CYAN}Play card (1-{len(playable_cards)}) or 'd' to draw: {Colors.END}").lower()
                
                if choice == 'd':
                    new_card = self.deck.draw_card()
                    if new_card:
                        player.add_card(new_card)
                        self.log_action(f"{player.name} drew a card")
                        
                        if new_card.can_play_on(self.get_top_card(), self.current_color):
                            play_choice = input(f"{Colors.YELLOW}Play drawn card ({new_card})? (y/n): {Colors.END}").lower()
                            if play_choice == 'y':
                                self.play_card(player, new_card)
                                return
                    
                    self.log_action(f"{player.name}'s turn skipped")
                    return
                
                card_index = int(choice) - 1
                if 0 <= card_index < len(playable_cards):
                    selected_card = playable_cards[card_index]
                    self.play_card(player, selected_card)
                    return
                else:
                    print(f"{Colors.RED}Invalid choice!{Colors.END}")
                    
            except ValueError:
                print(f"{Colors.RED}Enter a number or 'd'!{Colors.END}")
    
    def computer_turn(self, player: Player):
        print(f"{Colors.CYAN}{player.name} is thinking...{Colors.END}")
        time.sleep(1.5)
        
        playable_cards = player.get_playable_cards(self.get_top_card(), self.current_color)
        
        if not playable_cards:
            new_card = self.deck.draw_card()
            if new_card:
                player.add_card(new_card)
                self.log_action(f"{player.name} drew a card")
                
                if new_card.can_play_on(self.get_top_card(), self.current_color):
                    self.play_card(player, new_card)
                    return
            
            self.log_action(f"{player.name}'s turn skipped")
            return
        
        opponent = self.players[1 - self.current_player_index]
        game_state = {
            'top_card': self.get_top_card(),
            'current_color': self.current_color,
            'my_hand': player.hand,
            'opponent_hand_size': len(opponent.hand),
            'my_hand_size': len(player.hand),
            'deck_size': len(self.deck.cards)
        }
        
        result = player.ai_strategy.choose_card(playable_cards, game_state)
        
        if len(result) == 3:
            selected_card, wild_color_hint, reasoning = result
            self.log_action(f"{player.name}: {reasoning}")
        else:
            selected_card, wild_color_hint, reasoning = result[0], result[1], ""
        
        self.play_card(player, selected_card, wild_color_hint)
    
    def play_card(self, player: Player, card: Card, wild_color_hint: Optional[str] = None):
        player.remove_card(card)
        self.discard_pile.append(card)
        
        self.log_action(f"{player.name} played {card}")
        
        if card.card_type in [CardType.WILD, CardType.WILD_DRAW_FOUR]:
            if player.is_computer:
                self.current_color = player.ai_strategy.choose_wild_color(player.hand, wild_color_hint)
            else:
                while True:
                    color_choice = input(f"{Colors.YELLOW}Choose color ({Colors.RED}R{Colors.END}/{Colors.BLUE}B{Colors.END}/{Colors.GREEN}G{Colors.END}/{Colors.YELLOW}Y{Colors.END}): {Colors.END}").upper()
                    color_map = {'R': Color.RED, 'B': Color.BLUE, 'G': Color.GREEN, 'Y': Color.YELLOW}
                    if color_choice in color_map:
                        self.current_color = color_map[color_choice]
                        break
                    print(f"{Colors.RED}Use R, B, G, or Y!{Colors.END}")
            
            self.log_action(f"Color changed to {self.current_color.value}")
        else:
            self.current_color = card.color
        
        if card.card_type == CardType.SKIP:
            self.next_player()
            skipped_player = self.get_current_player()
            self.log_action(f"{skipped_player.name} was skipped")
        
        elif card.card_type == CardType.REVERSE:
            self.reverse_direction()
            self.log_action("Direction reversed")
        
        elif card.card_type == CardType.DRAW_TWO:
            self.next_player()
            target_player = self.get_current_player()
            for _ in range(2):
                new_card = self.deck.draw_card()
                if new_card:
                    target_player.add_card(new_card)
            self.log_action(f"{target_player.name} drew 2 cards")
        
        elif card.card_type == CardType.WILD_DRAW_FOUR:
            self.next_player()
            target_player = self.get_current_player()
            for _ in range(4):
                new_card = self.deck.draw_card()
                if new_card:
                    target_player.add_card(new_card)
            self.log_action(f"{target_player.name} drew 4 cards")
        
        if player.has_won():
            self.game_over = True
            self.winner = player
    
    def play_game(self):
        self.setup_game()
        
        while not self.game_over:
            self.display_game_state()
            
            current_player = self.get_current_player()
            
            if current_player.is_computer:
                self.computer_turn(current_player)
            else:
                self.human_turn(current_player)
            
            if not self.game_over:
                self.next_player()
            
            if self.deck.is_empty() and len(self.discard_pile) > 1:
                cards_to_reshuffle = self.discard_pile[:-1]
                self.discard_pile = [self.discard_pile[-1]]
                for card in cards_to_reshuffle:
                    self.deck.add_card(card)
                self.deck.shuffle()
                self.log_action("Deck reshuffled")
        
        self.clear_screen()
        print(f"{Colors.GREEN}{Colors.BOLD}🎊 GAME OVER! 🎊{Colors.END}")
        print(f"{Colors.GREEN}-{Colors.END}" * 30)
        print(f"{Colors.YELLOW}🏆 Winner: {Colors.BOLD}{self.winner.name}{Colors.END}")
        print()
        print(f"{Colors.CYAN}Final Scores:{Colors.END}")
        for player in self.players:
            player_name = f"{Colors.BOLD}{player.name}{Colors.END}" if not player.is_computer else f"{Colors.CYAN}{player.name}{Colors.END}"
            print(f"  {player_name}: {Colors.WHITE}{len(player.hand)} cards remaining{Colors.END}")
        print()

def display_startup_screen():
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"""
{Colors.PURPLE}
                                              
    {Colors.RED}██    ██ {Colors.BLUE}███    ██  {Colors.GREEN}██████{Colors.PURPLE}          
    {Colors.RED}██    ██ {Colors.BLUE}████   ██ {Colors.GREEN}██    ██{Colors.PURPLE}        
    {Colors.RED}██    ██ {Colors.BLUE}██ ██  ██ {Colors.GREEN}██    ██{Colors.PURPLE}        
    {Colors.RED}██    ██ {Colors.BLUE}██  ██ ██ {Colors.GREEN}██    ██{Colors.PURPLE}        
     {Colors.RED}██████  {Colors.BLUE}██   ████  {Colors.GREEN}██████{Colors.PURPLE}         
                                                
{Colors.BOLD}{Colors.WHITE}Cli-Based Card Game Interface{Colors.PURPLE}                                            
{Colors.END}
""")

def get_gemini_setup():
    print(f"{Colors.YELLOW}AI Opponent Setup{Colors.END}")
    print(f"{Colors.YELLOW}{'─'*35}{Colors.END}")
    print(f"""
{Colors.WHITE}To unlock the {Colors.RED}{Colors.BOLD}Genius AI{Colors.END}{Colors.WHITE} opponent, you need a Google Gemini API key.
This enables the most challenging AI experience powered by advanced AI!{Colors.END}
*Don’t have a Gemini API key? You can still play Easy and Medium levels without one.*
""")
    
    choice = input(f"{Colors.BOLD}Do you have a Gemini API key? (y/n): {Colors.END}").lower().strip()
    
    if choice == 'y':
        while True:
            api_key = input(f"\n{Colors.CYAN}Enter your Gemini API key: {Colors.END}").strip()
            if api_key:
                print(f"\n{Colors.GREEN}✅ API key configured successfully!{Colors.END}")
                print(f"{Colors.GREEN}🎯 Genius AI mode is now UNLOCKED!{Colors.END}")
                return api_key
            else:
                print(f"{Colors.RED}❌ Please enter a valid API key{Colors.END}")
    else:
        print(f"\n{Colors.YELLOW}⚠️  No problem! You can still play against Rookie and Smart AI.{Colors.END}")
        print(f"{Colors.WHITE}💡 You can add an API key later to unlock Genius AI.{Colors.END}")
        return None

def main():
    display_startup_screen()
    
    gemini_api_key = get_gemini_setup()
    
    input(f"\n{Colors.CYAN}Press Enter to continue to game setup...{Colors.END}")
    
    while True:
        try:
            game = UNOGame(gemini_api_key)
            game.play_game()
            
            print(f"\n{Colors.CYAN}🎮 PLAY AGAIN?{Colors.END}")
            print(f"{Colors.CYAN}{'─'*20}{Colors.END}")
            play_again = input(f"{Colors.WHITE}Would you like another game? (y/n): {Colors.END}").lower().strip()
            
            if play_again != 'y':
                print(f"\n{Colors.GREEN}🎯 Thanks for playing UNO!{Colors.END}")
                print(f"{Colors.YELLOW}Hope you had a great time! 👋{Colors.END}")
                break
                
        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}🛑 Game interrupted by user{Colors.END}")
            print(f"{Colors.GREEN}Thanks for playing! See you next time! 👋{Colors.END}")
            break
            
        except Exception as e:
            print(f"\n{Colors.RED}❌ An unexpected error occurred: {e}{Colors.END}")
            
            continue_choice = input(f"{Colors.CYAN}Would you like to try again? (y/n): {Colors.END}").lower().strip()
            if continue_choice != 'y':
                print(f"{Colors.YELLOW}Thanks for playing! 👋{Colors.END}")
                break

if __name__ == "__main__":
    main()
