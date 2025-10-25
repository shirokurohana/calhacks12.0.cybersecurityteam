// DYNAMICALLY FETCHES EMAILS & UPDATES THE PAGE

// Connecting JS -> Flask API
const emailContainer = document.getElementById('email-container');
const resultText = document.getElementById('result');
const scoreText = document.getElementById('score');
let score = 0;

async function loadEmail() {
  const response = await fetch('http://127.0.0.1:5000/api/email');
  const email = await response.json();

  emailContainer.innerHTML = `
    <p><strong>From:</strong> ${email.sender}</p>
    <p><strong>Subject:</strong> ${email.subject}</p>
    <p>${email.body}</p>
  `;

  document.getElementById('safe').onclick = () => checkAnswer(false, email.is_phish);
  document.getElementById('phish').onclick = () => checkAnswer(true, email.is_phish);
}

function checkAnswer(userGuess, actualPhish) {
  if (userGuess === actualPhish) {
    resultText.textContent = '✅ Correct!';
    score++;
  } else {
    resultText.textContent = '❌ Incorrect!';
  }
  scoreText.textContent = `Score: ${score}`;
  setTimeout(loadEmail, 1500);
}

loadEmail();
