import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import Select from 'react-select';
const plan = window.__PLAN;
const CITIES = ['Chicago, Illinois, United States', 'Chicago Heights, Illinois, United States'];
function Field({ f }) {
  const [v, setV] = useState('');
  const [touched, setT] = useState(false);
  const err = touched && f.required && !v ? <div className="helper-text--error">This field is required.</div> : null;
  const label = <label htmlFor={f.id}>{f.label}{f.required ? ' *' : ''}</label>;
  if (f.type === 'multi') {
    const [sel, setSel] = useState([]);
    return <fieldset className="field"><legend>{f.label}</legend>{f.options.map((o, i) => <div key={o}>
      <input type="checkbox" id={f.id + '_' + i} name={f.id} checked={sel.includes(o)} onChange={e => setSel(e.target.checked ? [...sel, o] : sel.filter(x => x !== o))} />
      <label htmlFor={f.id + '_' + i}>{o}</label></div>)}</fieldset>;
  }
  if (f.type === 'combo') {
    const opts = (f.key === 'country' ? [{ label: 'United States', value: 'US' }, { label: 'Canada', value: 'CA' }]
      : f.key === 'location' ? CITIES.map(c => ({ label: c, value: c }))
      : f.options.map(o => ({ label: o, value: o })));
    return <div className="field">{label}<Select inputId={f.id} classNamePrefix="select" options={opts}
      value={v || null} onChange={o => { setV(o); if (f.key === 'location') { document.getElementById('lat').value = '41.88'; } }}
      onBlur={() => setT(true)} isClearable={f.key !== 'country'}
      formatOptionLabel={f.key === 'country' ? (o, m) => m.context === 'value' ? '+1' : o.label : undefined} />
      {touched && f.required && !v ? <div className="helper-text--error">This field is required.</div> : null}</div>;
  }
  const P = { id: f.id, value: v, onChange: e => setV(e.target.value), onBlur: () => setT(true) };
  return <div className="field">{label}{f.type === 'textarea' ? <textarea {...P} /> : <input type="text" {...P} />}{err}</div>;
}
function App() {
  const [tick, setTick] = useState(0);
  window.__rerender = () => setTick(t => t + 1);   // simulate a re-render (e.g. after another widget changes)
  const [done, setDone] = useState(false);
  if (done) return <h1>Thank you for applying. Your application has been submitted.</h1>;
  return <form data-tick={tick} onSubmit={e => { e.preventDefault(); setDone(true); }}>{plan.map(f => <Field key={f.key} f={f} />)}
    <input type="hidden" name="latitude" id="lat" defaultValue="" />
    <button type="submit">Submit application</button></form>;
}
createRoot(document.getElementById('root')).render(<App />);
