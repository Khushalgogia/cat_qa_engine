import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const supabase = createClient(
  Deno.env.get('SUPABASE_URL')!,
  Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
)
const TELEGRAM_TOKEN = Deno.env.get('TELEGRAM_TOKEN')!
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

// ── Main handler ──────────────────────────────────────────

Deno.serve(async (req) => {
  if (req.method !== 'POST') return new Response('OK')

  const update = await req.json()
  if (!update.callback_query) return new Response('OK')

  const cq = update.callback_query
  const data: string = cq.data || ''
  const chatId = String(cq.message.chat.id)
  const messageId: number = cq.message.message_id

  // Only handle sprint callbacks
  if (!data.startsWith('sp|')) {
    await answerCallback(cq.id)
    return new Response('OK')
  }

  // Parse: sp|{session_id}|{option_index}
  const [, sessionId, optStr] = data.split('|')
  const selectedIndex = parseInt(optStr)

  // Load session
  const { data: session, error: sessErr } = await supabase
    .from('sprint_sessions')
    .select('*')
    .eq('id', sessionId)
    .single()

  if (sessErr || !session || session.completed) {
    await answerCallback(cq.id, 'Session expired.')
    return new Response('OK')
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
    await answerCallback(cq.id, 'Error loading question.')
    return new Response('OK')
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
    await answerCallback(cq.id, '❌ Wrong — added to debt queue!')
  } else {
    await answerCallback(cq.id, '✅ Correct!')
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
    return new Response('OK')
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
    return new Response('OK')
  }

  const total = newQueue.length
  const progress = `[${nextIndex + 1}/${total}]`
  const debtNote = newDebt > 0 ? `_Debt queue: +${newDebt}_ ⚠️\n\n` : ''
  const wrongNote = !isCorrect ? `_❌ That one will return. Keep going._\n\n` : ''

  const text = `⚡ *MATH SPRINT* ${progress}\n\n${debtNote}${wrongNote}${nextQ.question_text}`
  const keyboard = buildKeyboard(sessionId, nextQ.options as string[])

  await editMessage(chatId, messageId, text, keyboard)
  return new Response('OK')
})
