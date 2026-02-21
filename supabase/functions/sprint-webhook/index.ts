import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const supabase = createClient(
  Deno.env.get('SUPABASE_URL')!,
  Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
)
const TELEGRAM_TOKEN = Deno.env.get('TELEGRAM_TOKEN')!
const CHAT_ID = Deno.env.get('TELEGRAM_CHAT_ID')!
const BASE_URL = `https://api.telegram.org/bot${TELEGRAM_TOKEN}`

// ── Telegram helpers ──────────────────────────────────────

async function answerCallback(id: string, text = '') {
  await fetch(`${BASE_URL}/answerCallbackQuery`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ callback_query_id: id, text })
  })
}

async function editMessage(chatId: string, messageId: number, text: string, keyboard?: object) {
  const body: Record<string, unknown> = {
    chat_id: chatId,
    message_id: messageId,
    text,
    parse_mode: 'Markdown'
  }
  if (keyboard) body.reply_markup = keyboard

  await fetch(`${BASE_URL}/editMessageText`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
}

async function sendMessage(chatId: string, text: string) {
  await fetch(`${BASE_URL}/sendMessage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: chatId, text, parse_mode: 'Markdown' })
  })
}

function buildKeyboard(sessionId: string, options: string[]) {
  const buttons = options.map((opt, idx) => ({
    text: opt,
    callback_data: `sp|${sessionId}|${idx}`   // sp|{session_id}|{option_index}
  }))
  // 2x2 grid
  const rows = []
  for (let i = 0; i < buttons.length; i += 2) {
    rows.push(buttons.slice(i, i + 2))
  }
  return { inline_keyboard: rows }
}

// ── Poll Answer Handler (2 PM Spot the Flaw) ─────────────

async function handlePollAnswer(pollAnswer: { option_ids: number[] }) {
  const chosen = pollAnswer.option_ids
  if (!chosen || chosen.length === 0) return

  // Get today's problem ID from settings
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

  // Load the problem
  const { data: problem } = await supabase
    .from('qa_flaw_deck')
    .select('flawed_step_number, status')
    .eq('id', problemId)
    .single()

  if (!problem) {
    console.log(`Problem ${problemId} not found.`)
    return
  }

  // Already resolved — don't overwrite (idempotency guard)
  if (problem.status === 'caught' || problem.status === 'missed') {
    console.log(`Problem already resolved as '${problem.status}'. Skipping.`)
    return
  }

  const correctOption = problem.flawed_step_number - 1
  const isCaught = chosen[0] === correctOption
  const newStatus = isCaught ? 'caught' : 'missed'

  // Update qa_flaw_deck
  await supabase
    .from('qa_flaw_deck')
    .update({ status: newStatus })
    .eq('id', problemId)

  // Update daily_log
  await supabase
    .from('daily_log')
    .update({ caught: isCaught })
    .eq('problem_id', problemId)

  const emoji = isCaught ? '✅' : '❌'
  await sendMessage(CHAT_ID, `${emoji} Recorded as *${isCaught ? 'CAUGHT' : 'MISSED'}*.`)
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
  // Verify problem is still "missed" (guards against stale buttons)
  const { data: problem } = await supabase
    .from('qa_flaw_deck')
    .select('status')
    .eq('id', problemId)
    .single()

  if (!problem || problem.status !== 'missed') {
    await answerCallback(cqId, 'Already resolved.')
    return
  }

  if (action === 'got_it') {
    await supabase
      .from('qa_flaw_deck')
      .update({ status: 'reviewed' })
      .eq('id', problemId)

    await answerCallback(cqId, '✅ Graveyard cleared!')
    await editMessage(chatId, messageId,
      '✅ Graveyard cleared. That trap won\'t catch you again.')
    console.log(`Graveyard ${problemId.slice(0, 8)}... → reviewed`)
  } else {
    // "foggy" — leave as missed, it'll come back
    await answerCallback(cqId, '📌 Stays in graveyard')
    await editMessage(chatId, messageId,
      '📌 Still foggy — this one stays in the graveyard. It\'ll come back.')
    console.log(`Graveyard ${problemId.slice(0, 8)}... → stays missed`)
  }
}

// ── Sprint Handler (existing logic, unchanged) ───────────

async function handleSprintCallback(
  cqId: string,
  chatId: string,
  messageId: number,
  sessionId: string,
  selectedIndex: number
) {
  // Load session
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

  // Load current question
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

  // Log this answer
  await supabase.from('sprint_logs').insert({
    session_id: sessionId,
    question_id: currentQuestionId,
    category: question.category,
    is_correct: isCorrect,
    is_debt_attempt: currentIndex >= session.original_count
  })

  // Update question stats
  await supabase.from('math_sprints').update({
    times_attempted: question.times_attempted + 1,
    times_correct: isCorrect ? question.times_correct + 1 : question.times_correct
  }).eq('id', currentQuestionId)

  // Handle debt queue
  let newQueue = [...queue]
  let newDebt = session.debt_count

  if (!isCorrect) {
    newQueue.push(currentQuestionId)  // append to end
    newDebt += 1
    await answerCallback(cqId, '❌ Wrong — added to debt queue!')
  } else {
    await answerCallback(cqId, '✅ Correct!')
  }

  const nextIndex = currentIndex + 1

  // Update session
  await supabase.from('sprint_sessions').update({
    question_queue: newQueue,
    current_index: nextIndex,
    debt_count: newDebt
  }).eq('id', sessionId)

  // ── Sprint complete ─────────────────────────────────────
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

    await editMessage(chatId, messageId, summary)
    return
  }

  // ── Next question ───────────────────────────────────────
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

  await editMessage(chatId, messageId, text, keyboard)
}

// ── Main handler ──────────────────────────────────────────

Deno.serve(async (req) => {
  if (req.method !== 'POST') return new Response('OK')

  const update = await req.json()

  // ── Branch 1: Poll answer (2 PM Spot the Flaw) ─────────
  if (update.poll_answer) {
    await handlePollAnswer(update.poll_answer)
    return new Response('OK')
  }

  // ── Branch 2 & 3: Callback queries ─────────────────────
  if (!update.callback_query) return new Response('OK')

  const cq = update.callback_query
  const data: string = cq.data || ''
  const chatId = String(cq.message.chat.id)
  const messageId: number = cq.message.message_id

  // Sprint callback: sp|{session_id}|{option_index}
  if (data.startsWith('sp|')) {
    const [, sessionId, optStr] = data.split('|')
    await handleSprintCallback(cq.id, chatId, messageId, sessionId, parseInt(optStr))
    return new Response('OK')
  }

  // Graveyard callback: gy|{problem_id}|{action}
  if (data.startsWith('gy|')) {
    const [, problemId, action] = data.split('|')
    await handleGraveyardCallback(cq.id, chatId, messageId, problemId, action)
    return new Response('OK')
  }

  // Unknown callback — acknowledge silently
  await answerCallback(cq.id)
  return new Response('OK')
})
