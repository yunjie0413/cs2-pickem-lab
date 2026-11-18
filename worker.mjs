import { simulateStage } from './engine.mjs';
self.onmessage = ({ data }) => {
  try { self.postMessage({ result: simulateStage(data.event, data.options) }); }
  catch (error) { self.postMessage({ error: error.message }); }
};
