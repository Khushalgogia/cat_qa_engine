import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const supabase = createClient(
  Deno.env.get('SUPABASE_URL')!,
  Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
)
const TELEGRAM_TOKEN = Deno.env.get('TELEGRAM_TOKEN')!
const CHAT_ID = Deno.env.get('TELEGRAM_CHAT_ID')!
const BASE_URL = `https://api.telegram.org/bot${TELEGRAM_TOKEN}`

const FLAW_BUTTON_KEY = 'flaw_persistent_button_v1'
const FLAW_SESSION_KEY = 'flaw_session_v1'
const FLAW_POLL_REGISTRY_KEY = 'flaw_poll_registry_v1'
const FLAW_DAY_STATE_KEY = 'flaw_day_state_v1'

type FlawQueueItem = {
  problem_id: string
  is_revision: boolean
}

type FlawSession = {
  session_id: string
  selected_count: number
  queue: FlawQueueItem[]
  current_index: number
  current_problem_id: string | null
  current_log_id: string | null
  current_poll_id: string | null
  control_chat_id: string
  control_message_id: number
  created_at: string
  completed: boolean
}

// ── Telegram helpers ──────────────────────────────────────

async function tg(method: string, payload: Record<string, unknown>) {
  return await fetch(`${BASE_URL}/${method}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
}

async function answerCallback(id: string, text = '') {
  await tg('answerCallbackQuery', {
    callback_query_id: id,
    text
  })
}

async function editMessage(
  chatId: string,
  messageId: number,
  text: string,
  keyboard?: object,
  parseMode?: 'Markdown'
) {
  const body: Record<string, unknown> = {
    chat_id: chatId,
    message_id: messageId,
    text
  }
  if (keyboard) body.reply_markup = keyboard
  if (parseMode) body.parse_mode = parseMode

  await tg('editMessageText', body)
}

async function sendMessage(chatId: string, text: string, parseMode?: 'Markdown') {
  return await tg('sendMessage', {
    chat_id: chatId,
    text,
    ...(parseMode ? { parse_mode: parseMode } : {})
  })
}

async function sendPoll(
  chatId: string,
  question: string,
  options: string[],
  correctOptionId: number,
  explanation: string
) {
  return await tg('sendPoll', {
    chat_id: chatId,
    question,
    options,
    type: 'quiz',
    correct_option_id: correctOptionId,
    explanation,
    is_anonymous: false
  })
}

function buildKeyboard(sessionId: string, options: string[]) {
  const buttons = options.map((opt, idx) => ({
    text: opt,
    callback_data: `sp|${sessionId}|${idx}`
  }))
  const rows = []
  for (let i = 0; i < buttons.length; i += 2) {
    rows.push(buttons.slice(i, i + 2))
  }
  return { inline_keyboard: rows }
}

function buildFlawStartKeyboard() {
  return {
    inline_keyboard: [[
      { text: '▶️ Start Spot the Flaw', callback_data: 'flw|open' }
    ]]
  }
}

function buildFlawCountKeyboard() {
  return {
    inline_keyboard: [[
      { text: '1', callback_data: 'flc|1' },
      { text: '2', callback_data: 'flc|2' },
      { text: '3', callback_data: 'flc|3' },
      { text: '4', callback_data: 'flc|4' }
    ]]
  }
}

function buildFlawResumeKeyboard() {
  return {
    inline_keyboard: [[
      { text: '🔁 Session Active', callback_data: 'flw|resume' }
    ]]
  }
}

// ── Generic settings helpers ─────────────────────────────

async function getSettingValue(key: string) {
  const { data } = await supabase
    .from('settings')
    .select('value')
    .eq('key', key)
    .maybeSingle()
  return data?.value ?? null
}

async function putSettingValue(key: string, value: string) {
  await supabase.from('settings').upsert({ key, value })
}

async function getJsonSetting<T>(key: string, fallback: T): Promise<T> {
  const raw = await getSettingValue(key)
  if (!raw) return fallback
  try {
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

async function putJsonSetting(key: string, value: unknown) {
  await putSettingValue(key, JSON.stringify(value))
}

function todayIst() {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Kolkata',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).format(new Date())
}

function nowIsoIst() {
  return new Date().toLocaleString('sv-SE', { timeZone: 'Asia/Kolkata' }).replace(' ', 'T')
}

// ── Spot the Flaw helpers ────────────────────────────────

function pollOptionsForSteps(steps: string[]) {
  return steps.map((step, idx) => {
    const prefix = `Step ${idx + 1}: `
    const maxPreview = 100 - prefix.length - 3
    if (prefix.length + step.length > 100) {
      return `${prefix}${step.slice(0, maxPreview)}...`
    }
    return `${prefix}${step}`
  })
}

function pollExplanation(problem: Record<string, unknown>) {
  const errorCategory = String(problem.error_category ?? '')
  const explanation = String(problem.explanation ?? '')
  let text = `Trap: ${errorCategory}`
  if (text.length < 197) {
    const remaining = Math.max(0, 200 - text.length - 2)
    text = `${text}\n\n${explanation.slice(0, remaining)}`
  }
  return text.slice(0, 200)
}

function formatFlawMessage(problem: Record<string, unknown>, steps: string[], progress: string, isRevision: boolean) {
  const header = isRevision
    ? `📚 REVISION ROUND ${progress}\n\nYou saw this one before. Run the trap again.\n\n`
    : `🔍 SPOT THE FLAW ${progress}\n\n`
  const formattedSteps = steps.map((step, idx) => `Step ${idx + 1}: ${step}`).join('\n')
  const explanation = `Trap: ${String(problem.error_category ?? '')}\n${String(problem.explanation ?? '')}`
  return `${header}Problem:\n${String(problem.original_problem ?? '')}\n\nSteps:\n${formattedSteps}\n\nExplanation:\n${explanation}`
}

async function getButtonState() {
  return await getJsonSetting<Record<string, unknown> | null>(FLAW_BUTTON_KEY, null)
}

async function getFlawSession() {
  return await getJsonSetting<FlawSession | null>(FLAW_SESSION_KEY, null)
}

async function setFlawSession(session: FlawSession | null) {
  await putJsonSetting(FLAW_SESSION_KEY, session)
}

async function getPollRegistry() {
  return await getJsonSetting<Record<string, { session_id: string, problem_id: string, log_id: string, index: number }>>(
    FLAW_POLL_REGISTRY_KEY,
    {}
  )
}

async function setPollRegistry(registry: Record<string, unknown>) {
  await putJsonSetting(FLAW_POLL_REGISTRY_KEY, registry)
}

async function getDayState() {
  return await getJsonSetting<Record<string, Record<string, unknown>>>(FLAW_DAY_STATE_KEY, {})
}

async function setDayState(state: Record<string, unknown>) {
  await putJsonSetting(FLAW_DAY_STATE_KEY, state)
}

async function syncTodaysAnchor(dayRecord: Record<string, unknown>) {
  const problemId = String(dayRecord.most_recent_missed_problem_id || dayRecord.most_recent_answered_problem_id || '')
  const axiom = String(dayRecord.most_recent_missed_axiom || dayRecord.most_recent_answered_axiom || '')
  await putSettingValue('todays_problem_id', problemId)
  await putSettingValue('todays_axiom', axiom)
}

async function updateFlawDayState(problem: Record<string, unknown>, isCaught: boolean) {
  const state = await getDayState()
  const key = todayIst()
  const record = (state[key] ?? {}) as Record<string, unknown>

  record.most_recent_answered_problem_id = String(problem.id)
  record.most_recent_answered_axiom = String(problem.trap_axiom ?? '')
  record.most_recent_answered_caught = isCaught
  record.most_recent_answered_error_category = String(problem.error_category ?? '')
  record.last_answered_at = nowIsoIst()

  if (!isCaught) {
    record.most_recent_missed_problem_id = String(problem.id)
    record.most_recent_missed_axiom = String(problem.trap_axiom ?? '')
    record.most_recent_missed_error_category = String(problem.error_category ?? '')
    record.last_missed_at = nowIsoIst()
  }

  state[key] = record

  const sortedKeys = Object.keys(state).sort()
  while (sortedKeys.length > 14) {
    const oldest = sortedKeys.shift()
    if (oldest) delete state[oldest]
  }

  await setDayState(state)
  await syncTodaysAnchor(record)
}

async function selectFlawProblems(count: number): Promise<FlawQueueItem[]> {
  const { data: unseenRaw } = await supabase
    .from('qa_flaw_deck')
    .select('*')
    .eq('status', 'unseen')
    .order('source_file')
    .limit(50)

  const { data: deliveredRaw } = await supabase
    .from('qa_flaw_deck')
    .select('*')
    .eq('status', 'delivered')
    .order('delivered_at')
    .limit(50)

  const { data: missedRaw } = await supabase
    .from('qa_flaw_deck')
    .select('*')
    .eq('status', 'missed')
    .order('delivered_at')
    .limit(50)

  const unseen = (unseenRaw ?? []).filter((p) => Array.isArray(p.solution_steps) && p.solution_steps.length <= 10)
  const backlog = [...(deliveredRaw ?? []), ...(missedRaw ?? [])]
    .filter((p) => Array.isArray(p.solution_steps) && p.solution_steps.length <= 10)

  let unseenIdx = 0
  let backlogIdx = 0
  const used = new Set<string>()
  const queue: FlawQueueItem[] = []

  const takeUnseen = () => {
    while (unseenIdx < unseen.length) {
      const candidate = unseen[unseenIdx++]
      if (!used.has(candidate.id)) {
        used.add(candidate.id)
        return { problem_id: candidate.id as string, is_revision: false }
      }
    }
    return null
  }

  const takeBacklog = () => {
    while (backlogIdx < backlog.length) {
      const candidate = backlog[backlogIdx++]
      if (!used.has(candidate.id)) {
        used.add(candidate.id)
        return { problem_id: candidate.id as string, is_revision: true }
      }
    }
    return null
  }

  for (let slot = 0; slot < count; slot++) {
    const preferBacklog = slot === count - 1
    const item = preferBacklog
      ? (takeBacklog() ?? takeUnseen())
      : (takeUnseen() ?? takeBacklog())
    if (!item) break
    queue.push(item)
  }

  return queue
}

async function sendFlawQuestion(session: FlawSession) {
  const item = session.queue[session.current_index]
  const { data: problem } = await supabase
    .from('qa_flaw_deck')
    .select('*')
    .eq('id', item.problem_id)
    .single()

  if (!problem || !Array.isArray(problem.solution_steps) || problem.solution_steps.length === 0 || problem.solution_steps.length > 10) {
    throw new Error(`Problem unavailable or over limit: ${item.problem_id}`)
  }

  const nowIso = new Date().toISOString()
  if (!item.is_revision) {
    await supabase
      .from('qa_flaw_deck')
      .update({ status: 'delivered', delivered_at: nowIso })
      .eq('id', item.problem_id)
  } else {
    await supabase
      .from('qa_flaw_deck')
      .update({ delivered_at: nowIso })
      .eq('id', item.problem_id)
  }

  const { data: logRow } = await supabase
    .from('daily_log')
    .insert({
      problem_id: item.problem_id,
      is_revision: item.is_revision
    })
    .select('id')
    .single()

  const progress = `[${session.current_index + 1}/${session.queue.length}]`
  const detailText = formatFlawMessage(problem, problem.solution_steps as string[], progress, item.is_revision)
  const questionText = 'Which step contains the logical flaw?'.slice(0, 300)
  const options = pollOptionsForSteps(problem.solution_steps as string[])
  const explanation = pollExplanation(problem)

  const detailResp = await sendMessage(session.control_chat_id, detailText)
  if (!detailResp.ok) {
    throw new Error(`Failed to send flaw detail message: ${await detailResp.text()}`)
  }

  const pollResp = await sendPoll(
    session.control_chat_id,
    questionText,
    options,
    Number(problem.flawed_step_number) - 1,
    explanation
  )
  const pollJson = await pollResp.json()
  if (!pollResp.ok || !pollJson?.result?.poll?.id) {
    throw new Error(`Failed to send flaw poll: ${JSON.stringify(pollJson)}`)
  }

  session.current_problem_id = String(problem.id)
  session.current_log_id = String(logRow.id)
  session.current_poll_id = String(pollJson.result.poll.id)

  const registry = await getPollRegistry()
  registry[session.current_poll_id] = {
    session_id: session.session_id,
    problem_id: session.current_problem_id,
    log_id: session.current_log_id,
    index: session.current_index
  }
  await setPollRegistry(registry)
  await setFlawSession(session)

  await editMessage(
    session.control_chat_id,
    session.control_message_id,
    `🔍 Spot the Flaw session active [${session.current_index + 1}/${session.queue.length}]\n\nQuestion sent below.`,
    buildFlawResumeKeyboard()
  )
}

async function completeFlawSession(session: FlawSession) {
  session.completed = true
  await setFlawSession(null)
  await setPollRegistry({})

  await editMessage(
    session.control_chat_id,
    session.control_message_id,
    '✅ Spot the Flaw session complete.\n\nTap below to start another session today.',
    buildFlawStartKeyboard()
  )
}

async function startFlawSession(chatId: string, messageId: number, count: number, cqId: string) {
  const queue = await selectFlawProblems(count)
  if (queue.length === 0) {
    await answerCallback(cqId, 'No deliverable problems available.')
    await editMessage(chatId, messageId, '⚠️ No deliverable problems available right now.', buildFlawStartKeyboard())
    return
  }

  const session: FlawSession = {
    session_id: crypto.randomUUID(),
    selected_count: count,
    queue,
    current_index: 0,
    current_problem_id: null,
    current_log_id: null,
    current_poll_id: null,
    control_chat_id: chatId,
    control_message_id: messageId,
    created_at: nowIsoIst(),
    completed: false
  }

  await setFlawSession(session)
  await answerCallback(cqId, `Starting ${queue.length} question(s).`)
  await sendFlawQuestion(session)
}

async function handleFlawOpen(cqId: string, chatId: string, messageId: number) {
  const buttonState = await getButtonState()
  if (!buttonState || Number(buttonState.message_id) !== messageId) {
    await answerCallback(cqId, 'This button is stale.')
    return
  }

  const existingSession = await getFlawSession()
  if (existingSession && !existingSession.completed) {
    await answerCallback(cqId, 'Session already active. Continue with the current poll.')
    await editMessage(
      chatId,
      messageId,
      `🔍 Spot the Flaw session active [${existingSession.current_index + 1}/${existingSession.queue.length}]`,
      buildFlawResumeKeyboard()
    )
    return
  }

  await answerCallback(cqId, 'Choose question count.')
  await editMessage(
    chatId,
    messageId,
    '🔢 How many Spot the Flaw questions do you want right now?',
    buildFlawCountKeyboard()
  )
}

async function handleFlawCount(cqId: string, chatId: string, messageId: number, count: number) {
  const buttonState = await getButtonState()
  if (!buttonState || Number(buttonState.message_id) !== messageId) {
    await answerCallback(cqId, 'This picker is stale.')
    return
  }

  if (!Number.isInteger(count) || count < 1 || count > 4) {
    await answerCallback(cqId, 'Choose a number from 1 to 4.')
    return
  }

  const existingSession = await getFlawSession()
  if (existingSession && !existingSession.completed) {
    await answerCallback(cqId, 'Finish the current session first.')
    return
  }
  await startFlawSession(chatId, messageId, count, cqId)
}

async function handleFlawResume(cqId: string) {
  const existingSession = await getFlawSession()
  if (!existingSession || existingSession.completed) {
    await answerCallback(cqId, 'No active session right now.')
    return
  }
  await answerCallback(
    cqId,
    `Session in progress: question ${existingSession.current_index + 1} of ${existingSession.queue.length}.`
  )
}

async function handleFlawPollAnswer(pollAnswer: { poll_id: string, option_ids: number[] }) {
  const registry = await getPollRegistry()
  const mapping = registry[pollAnswer.poll_id]
  if (!mapping) {
    return false
  }

  const chosen = pollAnswer.option_ids
  if (!chosen || chosen.length === 0) return true

  const session = await getFlawSession()
  if (!session || session.completed || session.session_id !== mapping.session_id) {
    delete registry[pollAnswer.poll_id]
    await setPollRegistry(registry)
    return true
  }

  const { data: problem } = await supabase
    .from('qa_flaw_deck')
    .select('*')
    .eq('id', mapping.problem_id)
    .single()

  if (!problem) {
    delete registry[pollAnswer.poll_id]
    await setPollRegistry(registry)
    return true
  }

  const correctOption = Number(problem.flawed_step_number) - 1
  const isCaught = chosen[0] === correctOption
  const newStatus = isCaught ? 'caught' : 'missed'

  await supabase
    .from('qa_flaw_deck')
    .update({ status: newStatus })
    .eq('id', mapping.problem_id)

  await supabase
    .from('daily_log')
    .update({ caught: isCaught })
    .eq('id', mapping.log_id)

  await updateFlawDayState(problem, isCaught)

  const emoji = isCaught ? '✅' : '❌'
  await sendMessage(CHAT_ID, `${emoji} Recorded as ${isCaught ? 'CAUGHT' : 'MISSED'}.`)

  delete registry[pollAnswer.poll_id]
  await setPollRegistry(registry)

  const nextIndex = session.current_index + 1
  if (nextIndex >= session.queue.length) {
    await completeFlawSession(session)
    return true
  }

  session.current_index = nextIndex
  session.current_problem_id = null
  session.current_log_id = null
  session.current_poll_id = null
  await setFlawSession(session)
  await sendFlawQuestion(session)
  return true
}

// ── Legacy Poll Answer Handler ───────────────────────────

async function handleLegacyPollAnswer(pollAnswer: { option_ids: number[] }) {
  const chosen = pollAnswer.option_ids
  if (!chosen || chosen.length === 0) return

  const { data: setting } = await supabase
    .from('settings')
    .select('value')
    .eq('key', 'todays_problem_id')
    .single()

  if (!setting || !setting.value) {
    console.log('No todays_problem_id in settings. Ignoring poll answer.')
    return
  }

  const problemId = setting.value

  const { data: problem } = await supabase
    .from('qa_flaw_deck')
    .select('flawed_step_number, status')
    .eq('id', problemId)
    .single()

  if (!problem) {
    console.log(`Problem ${problemId} not found.`)
    return
  }

  if (problem.status === 'caught' || problem.status === 'missed') {
    console.log(`Problem already resolved as '${problem.status}'. Skipping.`)
    return
  }

  const correctOption = problem.flawed_step_number - 1
  const isCaught = chosen[0] === correctOption
  const newStatus = isCaught ? 'caught' : 'missed'

  await supabase
    .from('qa_flaw_deck')
    .update({ status: newStatus })
    .eq('id', problemId)

  await supabase
    .from('daily_log')
    .update({ caught: isCaught })
    .eq('problem_id', problemId)

  const emoji = isCaught ? '✅' : '❌'
  await sendMessage(CHAT_ID, `${emoji} Recorded as ${isCaught ? 'CAUGHT' : 'MISSED'}.`)
  console.log(`Poll answer processed: ${problemId.slice(0, 8)}... → '${newStatus}'`)
}

// ── Graveyard Callback Handler ────────────────────────────

async function handleGraveyardCallback(
  cqId: string,
  chatId: string,
  messageId: number,
  problemId: string,
  action: string
) {
  const { data: problem } = await supabase
    .from('qa_flaw_deck')
    .select('status')
    .eq('id', problemId)
    .single()

  if (!problem || (problem.status !== 'missed' && problem.status !== 'delivered')) {
    await answerCallback(cqId, 'Already resolved.')
    return
  }

  if (action === 'got_it') {
    await supabase
      .from('qa_flaw_deck')
      .update({ status: 'reviewed' })
      .eq('id', problemId)

    await answerCallback(cqId, '✅ Graveyard cleared!')
    await editMessage(chatId, messageId, '✅ Graveyard cleared. That trap won\'t catch you again.')
  } else {
    await supabase
      .from('qa_flaw_deck')
      .update({ status: 'missed' })
      .eq('id', problemId)

    await answerCallback(cqId, '📌 Stays in graveyard')
    await editMessage(chatId, messageId, '📌 Still foggy — this one stays in the graveyard. It\'ll come back.')
  }
}

// ── Sprint Handler (existing logic, preserved) ───────────

async function handleSprintCallback(
  cqId: string,
  chatId: string,
  messageId: number,
  sessionId: string,
  selectedIndex: number
) {
  const { data: session, error: sessErr } = await supabase
    .from('sprint_sessions')
    .select('*')
    .eq('id', sessionId)
    .single()

  if (sessErr || !session || session.completed) {
    await answerCallback(cqId, 'Session expired.')
    return
  }

  const queue: string[] = session.question_queue
  const currentIndex: number = session.current_index
  const currentQuestionId = queue[currentIndex]

  const { data: question } = await supabase
    .from('math_sprints')
    .select('*')
    .eq('id', currentQuestionId)
    .single()

  if (!question) {
    await answerCallback(cqId, 'Error loading question.')
    return
  }

  const isCorrect = selectedIndex === question.correct_answer_index

  await supabase.from('sprint_logs').insert({
    session_id: sessionId,
    question_id: currentQuestionId,
    category: question.category,
    is_correct: isCorrect,
    is_debt_attempt: currentIndex >= session.original_count
  })

  await supabase.from('math_sprints').update({
    times_attempted: question.times_attempted + 1,
    times_correct: isCorrect ? question.times_correct + 1 : question.times_correct
  }).eq('id', currentQuestionId)

  let newQueue = [...queue]
  let newDebt = session.debt_count

  if (!isCorrect) {
    newQueue.push(currentQuestionId)
    newDebt += 1
    await answerCallback(cqId, '❌ Wrong — added to debt queue!')
  } else {
    await answerCallback(cqId, '✅ Correct!')
  }

  const nextIndex = currentIndex + 1

  await supabase.from('sprint_sessions').update({
    question_queue: newQueue,
    current_index: nextIndex,
    debt_count: newDebt
  }).eq('id', sessionId)

  if (nextIndex >= newQueue.length) {
    await supabase.from('sprint_sessions').update({ completed: true }).eq('id', sessionId)

    let summary = `🏁 *Sprint Complete!*\n\n`
    summary += `Original questions: ${session.original_count}\n`
    if (newDebt > 0) {
      summary += `Debt repaid: ${newDebt} wrong answer(s) → ${newDebt} extra question(s)\n`
      summary += `Total answered: ${newQueue.length}\n\n`
      summary += `_Each wrong answer cost you an extra question. Tomorrow, go clean._`
    } else {
      summary += `✨ *Perfect run. Zero debt. Go get some sleep.*`
    }

    await editMessage(chatId, messageId, summary, undefined, 'Markdown')
    return
  }

  const nextQuestionId = newQueue[nextIndex]

  const { data: nextQ } = await supabase
    .from('math_sprints')
    .select('*')
    .eq('id', nextQuestionId)
    .single()

  if (!nextQ) {
    await editMessage(chatId, messageId, 'Error loading next question.')
    return
  }

  const total = newQueue.length
  const progress = `[${nextIndex + 1}/${total}]`
  const debtNote = newDebt > 0 ? `_Debt queue: +${newDebt}_ ⚠️\n\n` : ''
  const wrongNote = !isCorrect ? `_❌ That one will return. Keep going._\n\n` : ''

  const text = `⚡ *MATH SPRINT* ${progress}\n\n${debtNote}${wrongNote}${nextQ.question_text}`
  const keyboard = buildKeyboard(sessionId, nextQ.options as string[])

  await editMessage(chatId, messageId, text, keyboard, 'Markdown')
}

// ── Main handler ──────────────────────────────────────────

Deno.serve(async (req) => {
  if (req.method !== 'POST') return new Response('OK')

  const update = await req.json()

  if (update.poll_answer) {
    const handled = await handleFlawPollAnswer(update.poll_answer)
    if (!handled) {
      await handleLegacyPollAnswer(update.poll_answer)
    }
    return new Response('OK')
  }

  if (!update.callback_query) return new Response('OK')

  const cq = update.callback_query
  const data: string = cq.data || ''
  const chatId = String(cq.message.chat.id)
  const messageId: number = cq.message.message_id

  if (data.startsWith('sp|')) {
    const [, sessionId, optStr] = data.split('|')
    await handleSprintCallback(cq.id, chatId, messageId, sessionId, parseInt(optStr))
    return new Response('OK')
  }

  if (data.startsWith('gy|')) {
    const [, problemId, action] = data.split('|')
    await handleGraveyardCallback(cq.id, chatId, messageId, problemId, action)
    return new Response('OK')
  }

  if (data === 'flw|open') {
    await handleFlawOpen(cq.id, chatId, messageId)
    return new Response('OK')
  }

  if (data === 'flw|resume') {
    await handleFlawResume(cq.id)
    return new Response('OK')
  }

  if (data.startsWith('flc|')) {
    const [, countRaw] = data.split('|')
    await handleFlawCount(cq.id, chatId, messageId, parseInt(countRaw))
    return new Response('OK')
  }

  await answerCallback(cq.id)
  return new Response('OK')
})
