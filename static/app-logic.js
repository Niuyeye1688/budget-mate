// ========== Budget ==========
async function getMonthlyBudget() {
  return (await getConfig('monthly_budget', 0)) || 0;
}
async function setMonthlyBudget(amount) {
  await setConfig('monthly_budget', amount);
  return amount;
}
async function getCategoryLimits() {
  return (await getConfig('category_limits', {})) || {};
}
async function setCategoryLimit(category, amount) {
  const limits = await getCategoryLimits();
  limits[category] = amount;
  await setConfig('category_limits', limits);
  return amount;
}
async function getRemainingBudget() {
  return await getMonthlyBudget() - await getMonthSpent();
}

// ========== Records ==========
async function addRecord(amount, description, category, approved, reason = '') {
  const record = {
    id: Date.now(),
    date: new Date().toISOString().replace('T', ' ').slice(0, 19),
    amount: parseFloat(amount),
    description: description,
    category: category,
    approved: approved,
    reason: reason,
  };
  await dbAddRecord(record);
  return record;
}

async function getAllRecords() {
  return await dbGetAllRecords();
}

async function getMonthSpent() {
  const month = getCurrentMonth();
  const records = await getAllRecords();
  return records.reduce((s, r) => s + (r.date.startsWith(month) && r.approved ? r.amount : 0), 0);
}

async function getCategorySpent(category) {
  const month = getCurrentMonth();
  const records = await getAllRecords();
  return records.reduce((s, r) => s + (r.date.startsWith(month) && r.category === category && r.approved ? r.amount : 0), 0);
}

async function getCategorySpentRecent(category, hours = 1) {
  const cutoff = new Date(Date.now() - hours * 3600 * 1000);
  const records = await getAllRecords();
  let total = 0;
  for (const r of records) {
    if (!r.approved || r.category !== category) continue;
    const rd = new Date(r.date.replace(' ', 'T'));
    if (rd >= cutoff) total += r.amount;
  }
  return total;
}

async function getRecentRecords(category, minutes = 30) {
  const cutoff = new Date(Date.now() - minutes * 60000);
  const records = await getAllRecords();
  return records
    .filter(r => r.approved && r.category === category)
    .filter(r => new Date(r.date.replace(' ', 'T')) >= cutoff)
    .map(r => ({ amount: r.amount, description: r.description, date: r.date }));
}

async function getTodayRecords() {
  const today = new Date().toISOString().slice(0, 10);
  const records = await getAllRecords();
  return records.filter(r => r.date.startsWith(today));
}

async function getWeekRecords() {
  const now = new Date();
  const startOfWeek = new Date(now);
  startOfWeek.setDate(now.getDate() - now.getDay());
  startOfWeek.setHours(0, 0, 0, 0);
  const records = await getAllRecords();
  return records.filter(r => new Date(r.date.replace(' ', 'T')) >= startOfWeek);
}

function getCurrentMonth() {
  return new Date().toISOString().slice(0, 7);
}

async function clearAllRecords() {
  await dbClearRecords();
}

// ========== Category Detection ==========
function detectCategory(description) {
  const desc = description.toLowerCase();
  const keywords = {
    '餐饮': ['饭', '餐', '吃', '餐厅', '食堂', '外卖', '火锅', '烧烤', '咖啡', '奶茶', '菜', '请客', '聚餐', '酒', '食', '甜筒', '冰淇淋', '雪糕', '冰棍', '冰棒', '零食', '薯片', '饼干', '巧克力', '糖果', '面包', '蛋糕', '甜点', '甜品', '汉堡', '披萨', '炸鸡', '薯条', '小吃', '饮料', '可乐', '果汁', '矿泉水', '牛奶', '酸奶', '豆浆', '包子', '饺子', '面条', '米线', '河粉', '寿司', '沙拉', '粥', '油条', '煎饼', '烤肠'],
    '交通': ['车', '地铁', '公交', '出租', '滴滴', '打车', '加油', '油费', '停车', '高铁', '火车', '飞机', '票', '路费', '通勤'],
    '购物': ['买', '购物', '衣服', '鞋', '包', '化妆品', '超市', '便利店', '淘宝', '京东', '拼多多', '用品', '东西', '设备', '电器'],
    '娱乐': ['游戏', '电影', '唱', '玩', '旅游', '旅行', '门票', '会员', '视频', '音乐', '球', '健身', '娱乐', '休闲'],
  };
  for (const [cat, words] of Object.entries(keywords)) {
    for (const w of words) {
      if (desc.includes(w)) return cat;
    }
  }
  return '其他';
}

// ========== Rules ==========
async function checkRules(amount, category) {
  const limits = await getCategoryLimits();
  const catLimit = limits[category] || 0;
  const monthBudget = await getMonthlyBudget();
  const monthSpent = await getMonthSpent();
  const catSpent = await getCategorySpent(category);
  const catSpentRecent = await getCategorySpentRecent(category, 1);

  const reasons = [];
  let approved = true;

  if (monthBudget <= 0) {
    reasons.push('本月总预算未设置或为 0');
    approved = false;
  } else if (monthSpent + amount > monthBudget) {
    reasons.push(`本月已用 ${monthSpent.toFixed(2)} 元，加上这笔 ${amount.toFixed(2)} 元将超出总预算 ${monthBudget.toFixed(2)} 元`);
    approved = false;
  }

  // 分类上限不能超过月度总预算
  const effectiveCatLimit = catLimit > 0 ? Math.min(catLimit, monthBudget) : 0;
  if (effectiveCatLimit > 0 && catSpent + amount > effectiveCatLimit) {
    reasons.push(`【${category}】分类本月已用 ${catSpent.toFixed(2)} 元，上限为 ${effectiveCatLimit.toFixed(2)} 元`);
    approved = false;
  }

  if (effectiveCatLimit > 0 && catSpentRecent + amount > effectiveCatLimit) {
    reasons.push(`【${category}】最近1小时内已用 ${catSpentRecent.toFixed(2)} 元，加上这笔将超上限 ${effectiveCatLimit.toFixed(2)} 元`);
    approved = false;
  }

  // 短时高频限制：1小时内同分类累计不超过月度总预算的 10%
  const shortTermLimit = monthBudget * 0.1;
  if (catSpentRecent + amount > shortTermLimit) {
    reasons.push(`【${category}】最近1小时内已用 ${catSpentRecent.toFixed(2)} 元，加上这笔将超短时限额 ${shortTermLimit.toFixed(2)} 元`);
    approved = false;
  }

  return { approved, reasons, category };
}

// ========== AI Judge ==========
async function aiJudge(amount, description, recentItems, recentTotal) {
  const config = await getConfig('api_config', {});
  const apiKey = config.api_key || '';
  const baseUrl = config.base_url || 'https://api.deepseek.com';
  const model = config.model || 'deepseek-chat';

  if (!config.enabled || !apiKey) return null;

  const monthBudget = await getMonthlyBudget();
  const monthSpent = await getMonthSpent();
  const remaining = monthBudget - monthSpent;
  const limits = await getCategoryLimits();

  // 计算剩余天数和日均预算
  const today = new Date();
  const daysInMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate();
  const remainingDays = daysInMonth - today.getDate() + 1;
  const dailyBudget = remainingDays > 0 ? remaining / remainingDays : 0;
  const currentDate = `${today.getMonth() + 1}月${today.getDate()}日`;

  const catInfo = [];
  for (const [cat, limit] of Object.entries(limits)) {
    const spent = await getCategorySpent(cat);
    const recent = await getCategorySpentRecent(cat, 1);
    if (limit > 0) {
      catInfo.push(`${cat}: 本月已用${spent.toFixed(0)}元/上限${limit.toFixed(0)}元，最近1小时已用${recent.toFixed(0)}元`);
    } else {
      catInfo.push(`${cat}: 本月已用${spent.toFixed(0)}元/无上限，最近1小时已用${recent.toFixed(0)}元`);
    }
  }
  const catText = catInfo.length ? catInfo.join('；') : '暂无分类预算';

  let recentContext = '';
  if (recentItems && recentItems.length) {
    const lines = recentItems.map(i => `- ${i.description} ${i.amount.toFixed(0)}元`).join('\n');
    const totalWithCurrent = recentTotal + amount;
    recentContext = `\n本次外出您在同分类已消费：\n${lines}\n加上这笔【${description}】${amount.toFixed(0)}元，本次外出合计 ${totalWithCurrent.toFixed(0)} 元。\n`;
  }

  const prompt = `你是一位有鲜明个性的私人财务顾问，用户花钱前必须经你审批。你对合理的支出温柔体贴、热情鼓励，对浪费钱的行为则毫不留情地犀利吐槽。

语气要求：
- 如果批准：语气温柔亲切，像贴心闺蜜/兄弟一样，给用户满满的鼓励和认可
- 如果拒绝：语气犀利毒舌，直接指出问题，带一点"恨铁不成钢"的感觉\n\n用户当前财务状况：\n- 月预算：${monthBudget.toFixed(0)}元\n- 本月已用：${monthSpent.toFixed(0)}元\n- 本月剩余：${remaining.toFixed(0)}元\n- 今天是${currentDate}，本月还剩 ${remainingDays} 天\n- 日均可用预算：${dailyBudget.toFixed(0)}元（目标：月底之前预算不为零，保证每天正常吃饭）\n- 各分类使用情况：${catText}\n\n用户申请支出：${amount.toFixed(0)}元\n用途描述：${description}\n${recentContext}\n判断标准：\n1. 核心目标：让预算撑到月底不为零。日均可用预算 ${dailyBudget.toFixed(0)} 元是最重要的参考红线\n2. 餐饮类：正常一餐不应明显超过日均预算，超出需有正当理由（如聚餐、请客）。如果最近1小时内有其他餐饮消费，合并视为"本次一餐"判断\n3. 交通类：日常通勤单次不应超过日均预算的2倍，打车非急事应拒绝。如果最近1小时内有其他交通消费，合并视为"本次出行"判断\n4. 购物类：非必需品优先拒绝，奢侈品直接拒绝\n5. 娱乐类：每月不超过 2-3 次，单次不超过日均预算的3倍\n6. 明显浪费、冲动消费、可替代方案更便宜的 → 拒绝\n\n请根据用途描述判断属于哪个分类（餐饮/交通/购物/娱乐/其他）。\n输出严格JSON，不要有任何其他文字：\n{"approved": true/false, "reason": "简短理由（不超过30字）", "category": "分类名"}`;

  try {
    const resp = await fetch(`${baseUrl.replace(/\/$/, '')}/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${apiKey}` },
      body: JSON.stringify({ model, messages: [{ role: 'system', content: '你是一位有鲜明个性的私人财务顾问，对合理支出温柔鼓励，对浪费行为犀利吐槽。输出必须是JSON格式。' }, { role: 'user', content: prompt }], temperature: 0.3 }),
    });
    const result = await resp.json();
    let content = result.choices[0].message.content.trim();
    if (content.startsWith('```json')) content = content.slice(7);
    if (content.startsWith('```')) content = content.slice(3);
    if (content.endsWith('```')) content = content.slice(0, -3);
    content = content.trim();
    const parsed = JSON.parse(content);
    return {
      approved: !!parsed.approved,
      category: parsed.category || detectCategory(description),
      reason: parsed.reason || 'AI判断',
    };
  } catch (e) {
    console.error('AI judge error:', e);
    return null;
  }
}

async function aiClassify(description) {
  const config = await getConfig('api_config', {});
  const apiKey = config.api_key || '';
  const baseUrl = config.base_url || 'https://api.deepseek.com';
  const model = config.model || 'deepseek-chat';

  if (!config.enabled || !apiKey) return null;

  const prompt = `请判断以下消费描述属于哪个分类（餐饮/交通/购物/娱乐/其他），只输出分类名，不要其他文字。\n消费描述：${description}`;

  try {
    const resp = await fetch(`${baseUrl.replace(/\/$/, '')}/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${apiKey}` },
      body: JSON.stringify({ model, messages: [{ role: 'system', content: '你是一个消费分类助手，只输出分类名。' }, { role: 'user', content: prompt }], temperature: 0.1 }),
    });
    const result = await resp.json();
    let content = result.choices[0].message.content.trim();
    content = content.replace(/^["']|["']$/g, '').replace(/[【】]/g, '').trim();
    const validCats = ['餐饮', '交通', '购物', '娱乐', '其他'];
    if (validCats.includes(content)) return content;
    return null;
  } catch (e) {
    console.error('AI classify error:', e);
    return null;
  }
}

// ========== Judge Expense ==========
async function judgeExpense(amount, description) {
  const config = await getConfig('api_config', {});
  let category = detectCategory(description);

  const recentItems = await getRecentRecords(category, 30);
  const recentTotal = recentItems.reduce((s, i) => s + i.amount, 0);

  let tripPrefix = '';
  if (recentItems.length) {
    const tripTotal = recentTotal + amount;
    tripPrefix = `本次外出【${category}】合计 ${tripTotal.toFixed(2)} 元（含之前已审批的 ${recentTotal.toFixed(2)} 元）。`;
  }

  // AI 模式下直接让 AI 全权判断
  if (config.enabled && config.api_key) {
    const aiResult = await aiJudge(amount, description, recentItems, recentTotal);
    if (aiResult) {
      category = aiResult.category || category;
      let reason = aiResult.reason || 'AI判断通过';
      if (tripPrefix) reason = tripPrefix + reason;
      return { approved: aiResult.approved, category, reason };
    }
  }

  // Rule-based fallback
  const { approved: ruleApproved, reasons: ruleReasons } = await checkRules(amount, category);
  let reason = ruleReasons.join('；');
  if (tripPrefix) reason = tripPrefix + reason;
  return { approved: ruleApproved, category, reason };
}

// ========== Judge Batch ==========
async function judgeBatchExpense(items) {
  if (!items || !items.length) {
    return { approved: false, reason: '没有提交任何支出项', items: [] };
  }

  const totalAmount = items.reduce((s, i) => s + i.amount, 0);
  const combinedDesc = items.map(i => `${i.description} (${i.amount.toFixed(0)}元)`).join('；');
  const config = await getConfig('api_config', {});

  const itemResults = items.map(item => ({
    amount: item.amount,
    description: item.description,
    category: detectCategory(item.description),
  }));

  // AI 模式下让关键词未识别的 item 单独分类
  if (config.enabled && config.api_key) {
    await Promise.all(itemResults.map(async (item) => {
      if (item.category === '其他') {
        const aiCat = await aiClassify(item.description);
        if (aiCat) item.category = aiCat;
      }
    }));
  }

  // AI 模式下直接让 AI 全权判断
  if (config.enabled && config.api_key) {
    try {
      const aiResult = await aiJudge(totalAmount, `本次外出消费：${combinedDesc}`);
      if (aiResult) {
        return { approved: aiResult.approved, reason: aiResult.reason || 'AI判断通过', total: totalAmount, items: itemResults };
      }
    } catch (e) {
      console.error('AI batch judge error:', e);
    }
  }

  // Rule-based fallback
  const limits = await getCategoryLimits();
  const monthBudget = await getMonthlyBudget();
  const monthSpent = await getMonthSpent();

  const batchByCategory = {};
  for (const item of itemResults) {
    batchByCategory[item.category] = (batchByCategory[item.category] || 0) + item.amount;
  }

  const ruleReasons = [];
  let ruleApproved = true;

  if (monthBudget <= 0) {
    ruleReasons.push('本月总预算未设置或为 0');
    ruleApproved = false;
  } else if (monthSpent + totalAmount > monthBudget) {
    ruleReasons.push(`本次合计 ${totalAmount.toFixed(2)} 元，加上本月已用 ${monthSpent.toFixed(2)} 元将超出总预算 ${monthBudget.toFixed(2)} 元`);
    ruleApproved = false;
  }

  for (const [cat, batchAmount] of Object.entries(batchByCategory)) {
    const catLimit = limits[cat] || 0;
    const catSpent = await getCategorySpent(cat);
    const catSpentRecent = await getCategorySpentRecent(cat, 1);

    const effectiveCatLimit = catLimit > 0 ? Math.min(catLimit, monthBudget) : 0;
    if (effectiveCatLimit > 0 && catSpent + batchAmount > effectiveCatLimit) {
      ruleReasons.push(`【${cat}】分类本月已用 ${catSpent.toFixed(2)} 元，本次 ${batchAmount.toFixed(2)} 元将超上限 ${effectiveCatLimit.toFixed(2)} 元`);
      ruleApproved = false;
    }
    if (effectiveCatLimit > 0 && catSpentRecent + batchAmount > effectiveCatLimit) {
      ruleReasons.push(`【${cat}】最近1小时内已用 ${catSpentRecent.toFixed(2)} 元，本次 ${batchAmount.toFixed(2)} 元将超上限 ${effectiveCatLimit.toFixed(2)} 元`);
      ruleApproved = false;
    }

    const shortTermLimit = monthBudget * 0.15;
    if (catSpentRecent + batchAmount > shortTermLimit) {
      ruleReasons.push(`【${cat}】最近1小时内已用 ${catSpentRecent.toFixed(2)} 元，本次 ${batchAmount.toFixed(2)} 元将超短时限额 ${shortTermLimit.toFixed(2)} 元`);
      ruleApproved = false;
    }
  }

  if (ruleApproved && !ruleReasons.length) {
    ruleReasons.push(`本次消费合计 ${totalAmount.toFixed(2)} 元，余额充足，可以支出。`);
  }
  return { approved: ruleApproved, reason: ruleReasons.join('；'), total: totalAmount, items: itemResults };
}

// ========== Bills ==========
async function formatRecords(records) {
  const approved = records.filter(r => r.approved);
  if (!approved.length) return '  暂无记录';
  let total = 0;
  const lines = approved.map(r => {
    total += r.amount;
    return `  [${r.date}] ${r.amount.toFixed(2)} 元 | ${r.category} | ${r.description}`;
  });
  lines.push(`\n  合计支出: ${total.toFixed(2)} 元`);
  return lines.join('\n');
}

async function generateDailyBill() {
  const today = new Date().toISOString().slice(0, 10);
  const records = await getTodayRecords();
  const lines = [
    '='.repeat(window.innerWidth <= 600 ? 30 : 50),
    `[每日账单] ${today}`,
    '='.repeat(window.innerWidth <= 600 ? 30 : 50),
    await formatRecords(records),
    '='.repeat(window.innerWidth <= 600 ? 30 : 50),
    `[本月预算] ${(await getMonthlyBudget()).toFixed(2)} 元`,
    `[本月已用] ${(await getMonthSpent()).toFixed(2)} 元`,
    `[本月剩余] ${(await getRemainingBudget()).toFixed(2)} 元`,
    '='.repeat(window.innerWidth <= 600 ? 30 : 50),
  ];
  return lines.join('\n');
}

async function generateWeeklyBill() {
  const now = new Date();
  const weekday = now.getDay();
  const start = new Date(now);
  start.setDate(now.getDate() - weekday);
  const startStr = start.toISOString().slice(0, 10);
  const endStr = now.toISOString().slice(0, 10);
  const records = await getWeekRecords();

  const categoryStats = {};
  let total = 0;
  for (const r of records) {
    if (r.approved) {
      categoryStats[r.category] = (categoryStats[r.category] || 0) + r.amount;
      total += r.amount;
    }
  }

  const limits = await getCategoryLimits();
  const catLines = [];
  for (const [cat, spent] of Object.entries(categoryStats)) {
    const limit = limits[cat] || 0;
    if (limit > 0) {
      catLines.push(`  ${cat}: ${spent.toFixed(2)} 元 / ${limit.toFixed(2)} 元 (${(spent / limit * 100).toFixed(1)}%)`);
    } else {
      catLines.push(`  ${cat}: ${spent.toFixed(2)} 元 (无上限)`);
    }
  }

  const lines = [
    '='.repeat(window.innerWidth <= 600 ? 30 : 50),
    `[每周账单] ${startStr} 至 ${endStr}`,
    '='.repeat(window.innerWidth <= 600 ? 30 : 50),
    '【明细】',
    await formatRecords(records),
    '',
    '【分类统计】',
  ];
  if (catLines.length) lines.push(...catLines);
  else lines.push('  本周无支出');
  lines.push('', '【汇总】', `  本周总支出: ${total.toFixed(2)} 元`, `  本月预算: ${(await getMonthlyBudget()).toFixed(2)} 元`, `  本月剩余: ${(await getRemainingBudget()).toFixed(2)} 元`, '='.repeat(window.innerWidth <= 600 ? 30 : 50));
  return lines.join('\n');
}

async function generateMonthlyBill(month) {
  const records = await getAllRecords();
  const monthRecords = records.filter(r => r.date.startsWith(month));

  const categoryStats = {};
  let total = 0;
  for (const r of monthRecords) {
    if (r.approved) {
      categoryStats[r.category] = (categoryStats[r.category] || 0) + r.amount;
      total += r.amount;
    }
  }

  const limits = await getCategoryLimits();
  const catLines = [];
  for (const [cat, spent] of Object.entries(categoryStats)) {
    const limit = limits[cat] || 0;
    if (limit > 0) {
      catLines.push(`  ${cat}: ${spent.toFixed(2)} 元 / ${limit.toFixed(2)} 元 (${(spent / limit * 100).toFixed(1)}%)`);
    } else {
      catLines.push(`  ${cat}: ${spent.toFixed(2)} 元 (无上限)`);
    }
  }

  const remaining = (await getMonthlyBudget()) - total;
  const lines = [
    '='.repeat(window.innerWidth <= 600 ? 30 : 50),
    `[月度账单] ${month}`,
    '='.repeat(window.innerWidth <= 600 ? 30 : 50),
    '【明细】',
    await formatRecords(monthRecords),
    '',
    '【分类统计】',
  ];
  if (catLines.length) lines.push(...catLines);
  else lines.push('  本月无支出');
  lines.push('', '【汇总】', `  本月总支出: ${total.toFixed(2)} 元`, `  本月预算: ${(await getMonthlyBudget()).toFixed(2)} 元`, `  本月剩余: ${remaining.toFixed(2)} 元`, '='.repeat(window.innerWidth <= 600 ? 30 : 50));
  return lines.join('\n');
}

// ========== Meal Suggestion ==========
function _getMealByHour(hour) {
  const meals = [
    ['午餐', [...Array(6).keys()].map(i => i + 11)],
    ['晚餐', [...Array(7).keys()].map(i => i + 17).concat([...Array(11).keys()].map(i => i))],
  ];
  let remaining = [];
  let found = false;
  for (const [name, hours] of meals) {
    if (hours.includes(hour)) {
      found = true;
      remaining.push(name);
    } else if (found) {
      remaining.push(name);
    }
  }
  if (found) return [remaining[0], remaining];
  return [null, []];
}

async function getMealSuggestion() {
  const now = new Date();
  const hour = now.getHours();
  const [meal, remainingMeals] = _getMealByHour(hour);
  if (!meal) return { meal: null };

  // 如果当前餐段已有餐饮支出，不再提示
  const todayRecords = await getTodayRecords();
  const currentMealHours = meal === '午餐'
    ? [...Array(6).keys()].map(i => i + 11)
    : [...Array(7).keys()].map(i => i + 17).concat([...Array(11).keys()].map(i => i));
  const hasMeal = todayRecords.some(r => {
    if (r.category !== '餐饮' || !r.approved) return false;
    const rh = new Date(r.date.replace(' ', 'T')).getHours();
    return currentMealHours.includes(rh);
  });
  if (hasMeal) return { meal: null };

  const year = now.getFullYear();
  const month = now.getMonth() + 1;
  const lastDay = new Date(year, month, 0).getDate();
  const remainingDays = lastDay - now.getDate() + 1;

  const monthlyRemaining = await getRemainingBudget();
  const dailyBudget = monthlyRemaining / Math.max(remainingDays, 1);

  const todayRecords = await getTodayRecords();
  const dailySpent = todayRecords.filter(r => r.category === '餐饮' && r.approved).reduce((s, r) => s + r.amount, 0);

  const dailyLeft = Math.max(dailyBudget - dailySpent, 0);
  const remainingCount = remainingMeals.length;
  const suggestion = remainingCount > 0 ? dailyLeft / remainingCount : 0;

  // AI recommendations
  let recommendations = [];
  const config = await getConfig('api_config', {});
  if (config.enabled && config.api_key && navigator.onLine) {
    try {
      const preferences = config.dietary_preferences || '';
      recommendations = await aiRecommendMeal(meal, suggestion, preferences);
    } catch (e) {
      console.error('AI meal error:', e);
    }
  }

  return {
    meal,
    suggestion: Math.round(suggestion * 100) / 100,
    daily_budget: Math.round(dailyBudget * 100) / 100,
    daily_spent: Math.round(dailySpent * 100) / 100,
    remaining_days: Math.max(remainingDays, 1),
    recommendations,
  };
}

async function aiRecommendMeal(meal, budget, preferences) {
  const config = await getConfig('api_config', {});
  const apiKey = config.api_key || '';
  const baseUrl = config.base_url || 'https://api.deepseek.com';
  const model = config.model || 'deepseek-chat';

  const prefText = preferences ? `\n用户饮食偏好/忌口：${preferences}` : '';
  const prompt = `你是贴心的饮食顾问，帮用户推荐今天${meal}吃什么。\n\n用户预算：建议控制在 ${budget.toFixed(0)} 元内。${prefText}\n\n要求：\n1. 推荐 2-3 个符合预算的食物选项\n2. 每个选项包含：名称、预估价格（整数）、一句话推荐理由\n3. 推荐要接地气、实用，避开用户忌口的食物\n4. 如果预算很低（<15元），优先推荐省钱又饱腹的选择\n5. 如果预算充裕（>40元），可以推荐稍微丰富一点的\n\n输出严格JSON数组，不要有任何其他文字：\n[{"name": "选项名称", "price": 预估价格, "reason": "推荐理由"}]`;

  const resp = await fetch(`${baseUrl.replace(/\/$/, '')}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${apiKey}` },
    body: JSON.stringify({ model, messages: [{ role: 'system', content: '你是一个贴心的饮食顾问，帮助用户选择今天吃什么。输出必须是JSON格式。' }, { role: 'user', content: prompt }], temperature: 0.7 }),
  });
  const result = await resp.json();
  let content = result.choices[0].message.content.trim();
  if (content.startsWith('```json')) content = content.slice(7);
  if (content.startsWith('```')) content = content.slice(3);
  if (content.endsWith('```')) content = content.slice(0, -3);
  content = content.trim();
  const parsed = JSON.parse(content);
  return parsed.map(item => ({ name: item.name || '', price: parseInt(item.price || 0), reason: item.reason || '' }));
}

// ========== Monthly Reset ==========
async function checkMonthlyReset() {
  const currentMonth = getCurrentMonth();
  const storedMonth = await getConfig('current_month', '');

  if (storedMonth && storedMonth !== currentMonth) {
    const bill = await generateMonthlyBill(storedMonth);
    const bills = await getConfig('bills', {});
    bills[storedMonth] = bill;
    await setConfig('bills', bills);
    await clearAllRecords();
    await setConfig('current_month', currentMonth);
    console.log(`[月度重置] 已生成 ${storedMonth} 月度账单`);
  } else if (!storedMonth) {
    await setConfig('current_month', currentMonth);
  }
}

// ========== Budget API (for dashboard) ==========
async function getBudgetData() {
  const limits = await getCategoryLimits();
  const categories = [];
  const totalLimit = Object.values(limits).reduce((s, l) => s + (l > 0 ? l : 0), 0);

  const now = new Date();
  const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
  const remainingDays = lastDay - now.getDate() + 1;
  const dailyBudget = (await getRemainingBudget()) / Math.max(remainingDays, 1);

  for (const [cat, limit] of Object.entries(limits)) {
    const spent = await getCategorySpent(cat);
    const pct = limit > 0 ? (spent / limit * 100) : 0;
    let alloc = 0;
    if (totalLimit > 0 && limit > 0) {
      alloc = dailyBudget * (limit / totalLimit);
      const catRem = limit - spent;
      if (alloc > catRem) alloc = catRem;
    }
    categories.push({ name: cat, limit, spent, percent: Math.round(pct * 10) / 10, daily_alloc: alloc > 0 ? Math.round(alloc * 100) / 100 : 0 });
  }

  return {
    monthly_budget: await getMonthlyBudget(),
    month_spent: await getMonthSpent(),
    remaining: await getRemainingBudget(),
    daily_budget: Math.round(dailyBudget * 100) / 100,
    remaining_days: Math.max(remainingDays, 1),
    categories,
  };
}

// ========== Export / Import ==========
async function exportToJSON() {
  const data = await dbExportData();
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `budget_data_${new Date().toISOString().slice(0,10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

async function importFromJSON(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const data = JSON.parse(e.target.result);
        await dbImportData(data);
        resolve();
      } catch (err) {
        reject(err);
      }
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}
