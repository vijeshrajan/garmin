(() => {
  const pages = [...document.querySelectorAll('[data-panel]')];
  const aliases = {morning:'recovery',health:'recovery',training:'week',running:'progress',trends:'progress',goal:'progress',insights:'evidence',relationships:'evidence',coverage:'evidence',checkin:'today'};
  function route() {
    const hash = location.hash.slice(1) || 'today';
    const selected = aliases[hash] || (pages.some(p => p.dataset.panel === hash) ? hash : 'today');
    pages.forEach(p => p.hidden = p.dataset.panel !== selected);
    document.querySelectorAll('[data-page]').forEach(a => {
      if (a.dataset.page === selected) a.setAttribute('aria-current','page');
      else a.removeAttribute('aria-current');
    });
    const target = document.getElementById(hash);
    if (target && aliases[hash]) target.scrollIntoView({block:'start'});
    else window.scrollTo(0,0);
  }
  window.addEventListener('hashchange',route); route();
  document.getElementById('checkinForm').addEventListener('submit', event => {
    event.preventDefault();
    const feeling = document.getElementById('feeling').value;
    const minutes = document.getElementById('available').value;
    let title = ADVISOR.headline, text = ADVISOR.action;
    if (feeling === 'urgent') {
      title = 'Stop exercise and seek urgent help';
      text = 'Chest pain, fainting or severe breathlessness can need urgent medical care. Contact local emergency services. A watch score cannot assess these symptoms.';
    } else if (feeling === 'unwell') {
      title = 'Pause the training recommendation';
      text = 'Avoid a hard session while ill or experiencing pain. Seek clinical advice for new, persistent or worsening symptoms.';
    } else if (feeling === 'sore') {
      title = 'Reduce the demand today';
      text = 'Choose rest or gentle movement that feels comfortable. Reassess fatigue and soreness tomorrow before progressing.';
    } else if (feeling === 'well' && !ADVISOR.stale) {
      text += ` You have ${minutes} minutes available: use this as a time limit, keep effort conversational, and reassess after the first 10 minutes. This is an easy-session option, not a prescribed training plan.`;
    } else if (feeling === 'unknown') {
      text = 'Choose how you feel before using this guidance. '+ADVISOR.action;
    }
    document.getElementById('advisorDecision').textContent = title;
    document.getElementById('advisorAction').textContent = text;
    document.getElementById('checkinResult').textContent = title+'. '+text;
  });
})();
