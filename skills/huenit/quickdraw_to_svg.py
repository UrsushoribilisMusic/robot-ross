#!/usr/bin/env python3
"""
quickdraw_to_svg.py
-------------------
Fetch a sample from the Google Quick Draw dataset and convert to SVG.

Usage:
    python3 quickdraw_to_svg.py cat --out /tmp/cat.svg
    python3 quickdraw_to_svg.py "hot dog" --index 5
    python3 quickdraw_to_svg.py dog --seed 42
    python3 quickdraw_to_svg.py --list-categories
"""

import sys
import os
import json
import random
import argparse
import difflib
import urllib.request
import urllib.parse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR  = os.path.join(SCRIPT_DIR, "quickdraw_cache")
MAX_CACHED = 300   # stream this many samples from ndjson per category
BASE_URL   = "https://storage.googleapis.com/quickdraw_dataset/full/simplified"

# All 345 Quick Draw categories
QUICKDRAW_CATEGORIES = [
    "aircraft carrier", "airplane", "alarm clock", "ambulance", "angel",
    "animal migration", "ant", "anvil", "apple", "arm", "asparagus", "axe",
    "backpack", "banana", "bandage", "barn", "baseball", "baseball bat",
    "basket", "basketball", "bat", "bathtub", "beach", "bear", "beard",
    "bed", "bee", "belt", "bench", "bicycle", "binoculars", "bird",
    "blackberry", "blueberry", "book", "boomerang", "bottlecap", "bowtie",
    "bracelet", "brain", "bread", "bridge", "broccoli", "broom", "bucket",
    "bulldozer", "bus", "bush", "butterfly", "cactus", "cake", "calculator",
    "calendar", "camel", "camera", "camouflage", "campfire", "candle",
    "cannon", "canoe", "car", "carrot", "castle", "cat", "ceiling fan",
    "cell phone", "cello", "chair", "chandelier", "church", "circle",
    "clarinet", "clock", "cloud", "coffee cup", "compass", "computer",
    "cookie", "cooler", "couch", "cow", "crab", "crayon", "crocodile",
    "crown", "cruise ship", "cup", "diamond", "dishwasher", "diving board",
    "dog", "dolphin", "donut", "door", "dragon", "dresser", "drill",
    "drums", "duck", "dumbbell", "ear", "elbow", "elephant", "envelope",
    "eraser", "eye", "eyeglasses", "face", "fan", "feather", "fence",
    "finger", "fire hydrant", "fireplace", "firetruck", "fish", "flamingo",
    "flashlight", "flip flops", "floor lamp", "flower", "flying saucer",
    "foot", "fork", "frog", "frying pan", "garden", "garden hose",
    "giraffe", "goatee", "golf club", "grapes", "grass", "guitar",
    "hamburger", "hammer", "hand", "harp", "hat", "headphones", "hedgehog",
    "helicopter", "helmet", "hexagon", "hockey puck", "hockey stick",
    "horse", "hospital", "hot air balloon", "hot dog", "hot tub",
    "hourglass", "house", "house plant", "hurricane", "ice cream", "jacket",
    "jail", "kangaroo", "key", "keyboard", "knee", "knife", "ladder",
    "lantern", "laptop", "leaf", "leg", "light bulb", "lighthouse",
    "lightning", "line", "lion", "lipstick", "lobster", "lollipop",
    "mailbox", "map", "marker", "matches", "megaphone", "mermaid",
    "microphone", "microwave", "monkey", "moon", "mosquito", "motorbike",
    "mountain", "mouse", "moustache", "mouth", "mug", "mushroom", "nail",
    "necklace", "nose", "ocean", "octopus", "onion", "oven", "owl",
    "paintbrush", "palm tree", "panda", "pants", "paper clip", "parachute",
    "parrot", "passport", "peanut", "pear", "peas", "pencil", "penguin",
    "piano", "pickup truck", "picture frame", "pig", "pillow", "pizza",
    "plane", "pliers", "police car", "pond", "pool", "popsicle", "postcard",
    "potato", "power outlet", "purse", "rabbit", "raccoon", "radio", "rain",
    "rainbow", "rake", "remote control", "rhinoceros", "rifle", "river",
    "roller coaster", "rollerskates", "sailboat", "sandwich", "saxophone",
    "school bus", "scissors", "scorpion", "screwdriver", "sea turtle",
    "see saw", "shark", "sheep", "shoe", "shorts", "shovel", "sink",
    "skateboard", "skull", "skyscraper", "sleeping bag", "smiley face",
    "snail", "snake", "snorkel", "snowflake", "snowman", "soccer ball",
    "sock", "speedboat", "spider", "spoon", "spreadsheet", "square",
    "squiggle", "squirrel", "stairs", "star", "steak", "stereo",
    "stethoscope", "stitches", "stop sign", "stove", "strawberry",
    "streetlight", "string bean", "submarine", "suitcase", "sun", "swan",
    "sweater", "swing set", "sword", "syringe", "t-shirt", "table",
    "teapot", "teddy-bear", "telephone", "television", "tennis racquet",
    "tent", "The Eiffel Tower", "The Great Wall of China", "The Mona Lisa",
    "tiger", "toaster", "toe", "toilet", "tooth", "toothbrush",
    "toothpaste", "tornado", "tractor", "traffic light", "train", "tree",
    "triangle", "trombone", "truck", "trumpet", "umbrella", "underwear",
    "van", "vase", "violin", "washing machine", "watermelon", "waterslide",
    "wave", "whale", "wheel", "windmill", "wine bottle", "wine glass",
    "wristwatch", "yoga", "zebra", "zigzag",
]

_CATEGORIES_LOWER = [c.lower() for c in QUICKDRAW_CATEGORIES]

# Synonyms → Quick Draw category name (for words not in the dataset)
SYNONYMS = {
    "person": "face", "man": "face", "woman": "face", "guy": "face",
    "girl": "face", "boy": "face", "kid": "face", "child": "face",
    "people": "face", "human": "face", "lady": "face", "dude": "face",
    "sofa": "couch", "settee": "couch",
    "motorcycle": "motorbike", "moped": "motorbike", "scooter": "motorbike",
    "auto": "car", "vehicle": "car", "automobile": "car",
    "kitty": "cat", "kitten": "cat", "pussycat": "cat",
    "puppy": "dog", "pup": "dog", "doggy": "dog", "hound": "dog",
    "bunny": "rabbit", "bunny rabbit": "rabbit",
    "bird": "bird", "birdie": "bird",
    "mountain": "mountain", "hill": "mountain",
    "tree": "tree", "bush": "bush", "plant": "house plant",
    "flower": "flower", "rose": "flower", "daisy": "flower",
    "sun": "sun", "moon": "moon", "cloud": "cloud", "rain": "rain",
    "home": "house", "cabin": "house", "hut": "house",
    "pencil": "pencil", "pen": "pencil",
    "phone": "cell phone", "mobile": "cell phone", "smartphone": "cell phone",
    "laptop": "laptop", "computer": "computer", "pc": "computer",
    "tv": "television", "telly": "television",
    "fridge": "microwave", "stove": "stove",
}


def closest_category(prompt):
    """Return the best-matching Quick Draw category for a free-text prompt."""
    p = prompt.lower().strip()

    # Direct match
    if p in _CATEGORIES_LOWER:
        return QUICKDRAW_CATEGORIES[_CATEGORIES_LOWER.index(p)]

    # Synonym table
    if p in SYNONYMS:
        return SYNONYMS[p]

    # Word-level: check each word against synonyms then direct categories
    for word in p.split():
        if word in SYNONYMS:
            return SYNONYMS[word]
        if word in _CATEGORIES_LOWER:
            return QUICKDRAW_CATEGORIES[_CATEGORIES_LOWER.index(word)]

    # Fuzzy match — tighter cutoff to avoid bad matches
    matches = difflib.get_close_matches(p, _CATEGORIES_LOWER, n=1, cutoff=0.70)
    if matches:
        return QUICKDRAW_CATEGORIES[_CATEGORIES_LOWER.index(matches[0])]

    return None


def fetch_samples(category, max_samples=MAX_CACHED):
    """Download and cache up to max_samples recognized drawings for a category."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    safe = category.replace(" ", "_").lower()
    cache_file = os.path.join(CACHE_DIR, f"{safe}.json")

    if os.path.exists(cache_file):
        with open(cache_file) as f:
            return json.load(f)

    url = f"{BASE_URL}/{urllib.parse.quote(category)}.ndjson"
    print(f"  Downloading Quick Draw: '{category}' …")
    samples = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "robot-ross/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            for raw in resp:
                if not raw.strip():
                    continue
                obj = json.loads(raw)
                if obj.get("recognized", True):
                    samples.append(obj["drawing"])
                if len(samples) >= max_samples:
                    break
    except Exception as e:
        print(f"  ERROR fetching Quick Draw data: {e}")
        return []

    with open(cache_file, "w") as f:
        json.dump(samples, f)
    print(f"  Cached {len(samples)} samples for '{category}'")
    return samples


def strokes_to_svg(strokes, ox=0.0, oy=0.0, scale=1.0, viewbox=255):
    """
    Convert Quick Draw stroke format [[xs,ys], ...] to an SVG string.
    ox/oy shift the origin; scale multiplies coordinates.
    viewbox sets the SVG viewBox (default 255 = native Quick Draw space).
    """
    paths = []
    for stroke in strokes:
        xs, ys = stroke[0], stroke[1]
        if not xs:
            continue
        pts = [(ox + xs[i] * scale, oy + ys[i] * scale) for i in range(len(xs))]
        d = f"M {pts[0][0]:.2f},{pts[0][1]:.2f}"
        for px, py in pts[1:]:
            d += f" L {px:.2f},{py:.2f}"
        paths.append(f'  <path d="{d}" />')

    path_str = "\n".join(paths)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {viewbox} {viewbox}">\n'
        f'  <g fill="none" stroke="black" stroke-width="3"'
        f' stroke-linecap="round" stroke-linejoin="round">\n'
        f"{path_str}\n"
        f"  </g>\n"
        f"</svg>\n"
    )


def main():
    parser = argparse.ArgumentParser(description="Google Quick Draw → SVG")
    parser.add_argument("category", nargs="?", help="Category name or description")
    parser.add_argument("--out", default="/tmp/quickdraw_sketch.svg", help="Output SVG path")
    parser.add_argument("--index", type=int, default=None, help="Sample index (random if omitted)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--list-categories", action="store_true", help="Print all categories")
    args = parser.parse_args()

    if args.list_categories:
        for c in sorted(QUICKDRAW_CATEGORIES):
            print(c)
        return 0

    if not args.category:
        parser.error("category is required")

    cat = closest_category(args.category)
    if not cat:
        print(f"  ERROR: No Quick Draw category found for '{args.category}'")
        print("  Try --list-categories to see all options.")
        return 1

    if cat.lower() != args.category.lower():
        print(f"  Matched '{args.category}' → '{cat}'")

    samples = fetch_samples(cat)
    if not samples:
        print(f"  ERROR: Could not fetch samples for '{cat}'")
        return 1

    if args.seed is not None:
        random.seed(args.seed)

    idx = args.index if args.index is not None else random.randrange(len(samples))
    idx = idx % len(samples)
    strokes = samples[idx]

    svg = strokes_to_svg(strokes)
    with open(args.out, "w") as f:
        f.write(svg)

    n_strokes = len(strokes)
    n_pts = sum(len(s[0]) for s in strokes)
    print(f"  SVG: {args.out}  |  category: {cat}  |  {n_strokes} strokes, {n_pts} points")
    return 0


if __name__ == "__main__":
    sys.exit(main())
