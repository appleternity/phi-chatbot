# Agent 2 Testing Guide - User Story 1

## Overview
This guide validates the complete SmartphoneChatbot component implementation (Tasks T020-T029).

## Prerequisites
- Development server running at http://localhost:5173/
- Browser DevTools open (F12 or Cmd+Option+I)
- Application → Local Storage visible in DevTools

## Manual Testing Checklist

### Visual UI Tests

#### T020: ChatHeader Component
- [X] Header appears at top with sticky positioning
- [X] Avatar displays as gradient circle with first letter "T" for "Test Bot"
- [X] Display name "Test Bot" appears next to avatar
- [X] Status indicator shows "online" in gray text
- [X] Header has white background with bottom border

#### T021: MessageBubble Component
- [ ] User messages align to the right
- [ ] User messages have gradient background (purple-blue #667eea to #764ba2)
- [ ] User messages have white text
- [ ] Bot messages align to the left
- [ ] Bot messages have gray background (#e5e7eb)
- [ ] Bot messages have dark text (#111827)
- [ ] All messages have 18px border radius (rounded-[18px])
- [ ] Messages display timestamp in small gray text
- [ ] Long messages wrap correctly within 75% max width
- [ ] React.memo optimization verified (no re-renders on unrelated state changes)

#### T022: TypingIndicator Component
- [ ] Three gray dots appear when bot is typing
- [ ] Dots have staggered bounce animation (0ms, 200ms, 400ms delays)
- [ ] Animation runs smoothly with 1.4s duration
- [ ] Indicator has gray background with rounded corners

#### T023: MessageInput Component
- [ ] Input field appears at bottom with sticky positioning
- [ ] Input field has rounded-full styling (fully rounded)
- [ ] Placeholder text shows "Type a message..."
- [ ] Send button has gradient background matching user messages
- [ ] Send button text is white
- [ ] Input and button have white background container with top border
- [ ] Input focus shows blue ring (#667eea)

#### T028: Component Styles
- [ ] Custom scrollbar appears in message area (6px width)
- [ ] Scrollbar thumb is light gray (#cbd5e0)
- [ ] Scrollbar thumb darkens on hover (#a0aec0)
- [ ] Bounce animation works for typing indicator

### Functional Tests

#### T024: MessageList Component
- [ ] Messages display in scrollable container
- [ ] Container has correct padding (px-4 py-4)
- [ ] Auto-scroll works when at bottom of chat
- [ ] Auto-scroll stops when user scrolls up
- [ ] Typing indicator appears at bottom when isTyping=true
- [ ] Scroll anchor maintains position correctly

#### T025: useChatbot Hook
**Test 1: Send a message**
1. Type "Hello" in input field
2. Click Send button
3. Verify user message appears immediately with current timestamp
4. Verify typing indicator appears
5. Wait 1-2 seconds
6. Verify bot response appears with timestamp
7. Verify typing indicator disappears

**Test 2: Multiple messages**
1. Send 5 messages in quick succession
2. Verify all messages appear in correct order
3. Verify each has unique message ID
4. Verify timestamps increase sequentially

**Test 3: Error handling**
- [ ] Error message displays if chatbotService fails
- [ ] Error appears in red banner above input
- [ ] Chat remains functional after error

**Test 4: Enter key handling**
1. Type message in input
2. Press Enter key (without Shift)
3. Verify message sends
4. Verify input clears after send

**Test 5: Disabled state**
1. Send a message
2. Verify input and button disabled during bot response
3. Verify both re-enable after response received

#### T026: useLocalStorage Hook
**Test 1: Save to localStorage**
1. Send 3 messages
2. Open DevTools → Application → Local Storage
3. Verify "chatbot-comparison-session" key exists
4. Verify session data contains messages array
5. Verify bot1 chatId present
6. Verify messages have correct structure

**Test 2: Load from localStorage**
1. Send 3 messages (creates localStorage data)
2. Refresh page (Cmd+R or F5)
3. Verify all 3 messages restore correctly
4. Verify timestamps preserved
5. Verify message order preserved

**Test 3: Persistence across sessions**
1. Send messages
2. Close browser tab
3. Open http://localhost:5173/ in new tab
4. Verify messages restore

**Test 4: Debounced writes**
1. Send 10 messages rapidly
2. Check DevTools Network tab for localStorage writes
3. Verify writes are debounced (not 10 separate writes)

#### T027: SmartphoneChatbot Main Component
- [ ] Component has max width of 414px (iPhone size)
- [ ] Component has min height of 667px (iPhone size)
- [ ] Component has white background
- [ ] Component has rounded corners
- [ ] Component has shadow-lg (large shadow)
- [ ] Component has gray border
- [ ] All subcomponents render correctly
- [ ] Error banner appears above input when error occurs

#### T029: App Integration
- [ ] Page title shows "Chatbot Annotation Interface"
- [ ] Title is centered with large bold font (text-3xl)
- [ ] Single chatbot centered on gray background
- [ ] Chatbot has proper spacing (p-8)
- [ ] Session ID generates on first load
- [ ] Session persists in localStorage

### Integration Tests

**Test 1: Complete user flow**
1. Load http://localhost:5173/
2. Verify chatbot renders with "Test Bot" header
3. Type "What is your name?" and send
4. Verify message appears in blue-purple gradient
5. Wait for bot response
6. Verify bot response appears in gray
7. Send 3 more messages
8. Refresh page
9. Verify all 4 user messages and 4 bot responses restore

**Test 2: localStorage data structure**
```json
{
  "chatbot-comparison-session": {
    "sessionId": "uuid-here",
    "chatbots": [
      {
        "chatId": "bot1",
        "displayName": "Test Bot",
        "messages": [
          {
            "id": "msg_timestamp_random",
            "content": "Hello",
            "sender": "user",
            "timestamp": "2025-11-06T11:20:00.000Z"
          }
        ],
        "state": "idle"
      }
    ],
    "selection": {
      "selectedChatbotId": null,
      "timestamp": "2025-11-06T11:20:00.000Z"
    },
    "metadata": {
      "createdAt": "2025-11-06T11:20:00.000Z",
      "updatedAt": "2025-11-06T11:20:00.000Z",
      "version": "1.0.0"
    }
  }
}
```

**Test 3: Performance**
- [ ] Initial render completes in <100ms
- [ ] Message send feels instant (no lag)
- [ ] Typing indicator appears immediately
- [ ] Scroll is smooth without jank
- [ ] localStorage operations <50ms

### Edge Cases

**Test 1: Long messages**
1. Send a 500-character message
2. Verify message wraps correctly
3. Verify bubble doesn't exceed 75% width
4. Verify text is readable

**Test 2: Special characters**
1. Send message with emojis: "Hello 👋 🎉"
2. Send message with HTML: "<script>alert('test')</script>"
3. Send message with newlines: "Line 1\nLine 2\nLine 3"
4. Verify all display correctly without breaking UI

**Test 3: Rapid messaging**
1. Send 20 messages as fast as possible
2. Verify UI doesn't break
3. Verify all messages appear
4. Verify typing indicators work correctly

**Test 4: Empty states**
1. Clear localStorage manually
2. Refresh page
3. Verify empty chat loads without errors
4. Send first message
5. Verify everything works

## Expected Console Output

No errors or warnings should appear in browser console.

If there are warnings, document them in the report.

## Browser Testing

Test in all major browsers:
- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Edge (latest)

## Success Criteria

All checkboxes marked [X] = User Story 1 Complete ✅

## Common Issues and Solutions

### Issue: Messages don't persist
- Check DevTools → Application → Local Storage
- Verify "chatbot-comparison-session" key exists
- Check browser localStorage quota

### Issue: Typing indicator doesn't animate
- Verify styles.css imported in main.tsx
- Check Tailwind CSS compiled correctly
- Inspect animation-delay CSS properties

### Issue: Scroll doesn't auto-scroll
- Check react-intersection-observer installation
- Verify bottomRef and anchorRef both present
- Check inView state in DevTools React tab

### Issue: Enter key doesn't send message
- Verify onKeyPress handler attached
- Check e.key === 'Enter' condition
- Ensure !e.shiftKey check works

## Report Template

Copy this template for final report:

```markdown
## Agent 2 Testing Results

### Visual Tests
- ChatHeader: ✅/❌ [notes]
- MessageBubble: ✅/❌ [notes]
- TypingIndicator: ✅/❌ [notes]
- MessageInput: ✅/❌ [notes]

### Functional Tests
- Send message: ✅/❌ [notes]
- Typing indicator: ✅/❌ [notes]
- LocalStorage save: ✅/❌ [notes]
- LocalStorage load: ✅/❌ [notes]
- Auto-scroll: ✅/❌ [notes]

### Integration Tests
- Complete user flow: ✅/❌ [notes]
- Data structure: ✅/❌ [notes]
- Performance: ✅/❌ [notes]

### Edge Cases
- Long messages: ✅/❌ [notes]
- Special characters: ✅/❌ [notes]
- Rapid messaging: ✅/❌ [notes]

### Browser Compatibility
- Chrome: ✅/❌
- Firefox: ✅/❌
- Safari: ✅/❌
- Edge: ✅/❌

### Issues Found
1. [Issue description and resolution]
2. [Issue description and resolution]

### Screenshots
[Attach screenshots of working UI]

### Conclusion
User Story 1 Status: ✅ Complete / ❌ Incomplete
```
