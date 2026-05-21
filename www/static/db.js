const DB_NAME = 'budget-mate-db';
const DB_VERSION = 1;
let useLocalStorage = false;
let useMemory = false;
const memoryStore = {};
let memoryRecords = [];

function _isLocalStorageAvailable() {
  try {
    const test = '__test__';
    localStorage.setItem(test, test);
    localStorage.removeItem(test);
    return true;
  } catch (e) {
    return false;
  }
}

function openDB() {
  return new Promise((resolve, reject) => {
    if (!window.indexedDB) {
      reject(new Error('indexedDB not available'));
      return;
    }
    let settled = false;
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onerror = () => {
      if (!settled) { settled = true; reject(req.error); }
    };
    req.onsuccess = () => {
      if (!settled) { settled = true; resolve(req.result); }
    };
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
    setTimeout(() => {
      if (!settled) { settled = true; reject(new Error('IndexedDB open timeout')); }
    }, 2000);
  });
}

async function _initStorage() {
  if (useLocalStorage || useMemory) return;
  try {
    const db = await openDB();
    const testKey = '__db_test__';
    const testVal = Date.now();

    await new Promise((resolve, reject) => {
      const tx = db.transaction('config', 'readwrite');
      const store = tx.objectStore('config');
      const req = store.put({ key: testKey, value: testVal });
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
      setTimeout(() => reject(new Error('write timeout')), 2000);
    });

    const readBack = await new Promise((resolve, reject) => {
      const tx = db.transaction('config', 'readonly');
      const store = tx.objectStore('config');
      const req = store.get(testKey);
      req.onsuccess = () => resolve(req.result ? req.result.value : null);
      req.onerror = () => reject(req.error);
      setTimeout(() => reject(new Error('read timeout')), 2000);
    });

    if (readBack !== testVal) throw new Error('read/write mismatch');

    await new Promise((resolve, reject) => {
      const tx = db.transaction('config', 'readwrite');
      const store = tx.objectStore('config');
      const req = store.delete(testKey);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
      setTimeout(() => reject(new Error('delete timeout')), 2000);
    });
  } catch (e) {
    console.warn('[db] IndexedDB transaction test failed, falling back:', e.message);
    if (_isLocalStorageAvailable()) {
      useLocalStorage = true;
    } else {
      console.warn('[db] localStorage not available, using memory');
      useMemory = true;
    }
  }
}

async function getConfig(key, defaultValue) {
  await _initStorage();
  if (useMemory) {
    return key in memoryStore ? memoryStore[key] : defaultValue;
  }
  if (useLocalStorage) {
    try {
      const raw = localStorage.getItem('bm_' + key);
      return raw !== null ? JSON.parse(raw) : defaultValue;
    } catch (e) {
      return defaultValue;
    }
  }
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
  await _initStorage();
  if (useMemory) {
    memoryStore[key] = value;
    return;
  }
  if (useLocalStorage) {
    localStorage.setItem('bm_' + key, JSON.stringify(value));
    return;
  }
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('config', 'readwrite');
    const store = tx.objectStore('config');
    store.put({ key, value });
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function dbGetAllRecords() {
  await _initStorage();
  if (useMemory) return memoryRecords;
  if (useLocalStorage) {
    try {
      const raw = localStorage.getItem('bm_records');
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      return [];
    }
  }
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
  await _initStorage();
  if (useMemory) {
    memoryRecords.push(record);
    return;
  }
  if (useLocalStorage) {
    const records = await dbGetAllRecords();
    records.push(record);
    localStorage.setItem('bm_records', JSON.stringify(records));
    return;
  }
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('records', 'readwrite');
    const store = tx.objectStore('records');
    store.add(record);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function dbClearRecords() {
  await _initStorage();
  if (useMemory) {
    memoryRecords = [];
    return;
  }
  if (useLocalStorage) {
    localStorage.removeItem('bm_records');
    return;
  }
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('records', 'readwrite');
    const store = tx.objectStore('records');
    store.clear();
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function dbDeleteRecord(id) {
  await _initStorage();
  if (useMemory) {
    memoryRecords = memoryRecords.filter(r => r.id !== id);
    return;
  }
  if (useLocalStorage) {
    const records = await dbGetAllRecords();
    const filtered = records.filter(r => r.id !== id);
    localStorage.setItem('bm_records', JSON.stringify(filtered));
    return;
  }
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('records', 'readwrite');
    const store = tx.objectStore('records');
    store.delete(id);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
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
    if (useMemory) {
      memoryRecords = data.records.slice();
    } else if (useLocalStorage) {
      localStorage.setItem('bm_records', JSON.stringify(data.records));
    } else {
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
  }
  if (data.monthly_budget !== undefined) await setConfig('monthly_budget', data.monthly_budget);
  if (data.category_limits !== undefined) await setConfig('category_limits', data.category_limits);
  if (data.api_config !== undefined) await setConfig('api_config', data.api_config);
  if (data.current_month !== undefined) await setConfig('current_month', data.current_month);
}
