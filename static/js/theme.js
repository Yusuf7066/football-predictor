function toggleTheme() {
  document.body.classList.toggle('dark');
  localStorage.setItem('theme', document.body.classList.contains('dark') ? 'dark' : 'light');
}

window.onload = () => {
  const savedTheme = localStorage.getItem('theme');
  if (savedTheme === 'dark') {
    document.body.classList.add('dark');
  }

  const toggleButton = document.getElementById('darkToggle');
  if (toggleButton) {
    toggleButton.addEventListener('click', toggleTheme);
  } else {
    console.warn('Dark Mode toggle button not found');
  }
};
