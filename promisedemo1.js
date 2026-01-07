// Bubble Shooter Number Game using Promise

const TOTAL_SHOTS = 696969;
let score = 0;

// Promise that shoots one bubble and returns a random number (1–10)
function shootBubble() {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      const bubbleOne = Math.floor(Math.random() * 10) + 1; // 1–10
      resolve(bubbleOne);
    }, 500); // simulate delay like a game shot
  });
}

// Game logic
let game = Promise.resolve();

for (let i = 1; i <= TOTAL_SHOTS; i++) {
  game = game.then(() => {
    return shootBubble().then((bubbleOne) => {
      console.log(`Bubble ${i} shot: ${bubbleOne}`);
      score += bubbleOne;
    });
  });
}

// Final score
game.then(() => {
  console.log("Final Score:", score);
});
