function toggleTheme() {
  document.body.classList.toggle('dark');
  try {
    localStorage.setItem('theme', document.body.classList.contains('dark') ? 'dark' : 'light');
  } catch (e) {
    console.warn("⚠️ Theme preference couldn't be saved to localStorage.", e);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  try {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
      document.body.classList.add('dark');
    }
  } catch (e) {
    console.warn("⚠️ Failed to load theme from localStorage.", e);
  }

  const toggleBtn = document.getElementById('dark-mode-toggle');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', toggleTheme);
  }
});
