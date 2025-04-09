function toggleTheme() {
  document.body.classList.toggle('dark');
  localStorage.setItem('theme', document.body.classList.contains('dark') ? 'dark' : 'light');
}

window.onload = () => {
  // Apply stored theme
  if (localStorage.getItem('theme') === 'dark') {
    document.body.classList.add('dark');
  }

  // Attach toggle function to button
  const toggleButton = document.getElementById('darkToggle');
  if (toggleButton) {
    toggleButton.addEventListener('click', toggleTheme);
  }
};
