const DB_NAME = 'budget-mate-db';
const DB_VERSION = 1;

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onerror = () => reject(req.error);
    req.onsuccess = () => resolve(req.result);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains('records')) {
        const store = db.createObjectStore('records', { keyPath: 'id', autoIncrement: true });
        store.createIndex('date', 'date', { unique: false });
      }
      if (!db.objectStoreNames.contains('config')) {
        db.createObjectStore('config', { keyPath: 'key' });
      }
    };
  });
}

async function getConfig(key, defaultValue) {
  const db = await openDB();
  return new Promise((resolve) => {
    const tx = db.transaction('config', 'readonly');
    const store = tx.objectStore('config');
    const req = store.get(key);
    req.onsuccess = () => resolve(req.result ? req.result.value : defaultValue);
    req.onerror = () => resolve(defaultValue);
  });
}

async function setConfig(key, value) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('config', 'readwrite');
    const store = tx.objectStore('config');
    const req = store.put({ key, value });
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

async function dbGetAllRecords() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('records', 'readonly');
    const store = tx.objectStore('records');
    const req = store.getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function dbAddRecord(record) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('records', 'readwrite');
    const store = tx.objectStore('records');
    const req = store.add(record);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function dbClearRecords() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('records', 'readwrite');
    const store = tx.objectStore('records');
    const req = store.clear();
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

async function dbExportData() {
  const records = await dbGetAllRecords();
  const configKeys = ['monthly_budget', 'category_limits', 'api_config', 'current_month'];
  const config = {};
  for (const key of configKeys) {
    config[key] = await getConfig(key);
  }
  return { records, ...config };
}

async function dbImportData(data) {
  if (data.records && Array.isArray(data.records)) {
    await dbClearRecords();
    const db = await openDB();
    const tx = db.transaction('records', 'readwrite');
    const store = tx.objectStore('records');
    for (const r of data.records) {
      store.put(r);
    }
    await new Promise((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }
  if (data.monthly_budget !== undefined) await setConfig('monthly_budget', data.monthly_budget);
  if (data.category_limits !== undefined) await setConfig('category_limits', data.category_limits);
  if (data.api_config !== undefined) await setConfig('api_config', data.api_config);
  if (data.current_month !== undefined) await setConfig('current_month', data.current_month);
}
