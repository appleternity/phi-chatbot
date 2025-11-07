# Smoke Test Checklist

Complete manual testing checklist for the Chatbot Annotation Interface across all major browsers.

## Pre-Testing Setup

- [ ] Clear browser cache and localStorage
- [ ] Open browser developer console (F12)
- [ ] Verify no console errors on initial load

---

## Chrome Testing

### Basic Functionality
- [ ] Application loads without errors
- [ ] 3 chatbots render correctly (GPT-4, Claude, Gemini)
- [ ] Instagram-style gradient UI displays properly
- [ ] No console errors or warnings

### Message Interaction
- [ ] Send message to Bot 1 (GPT-4)
- [ ] Send message to Bot 2 (Claude)
- [ ] Send message to Bot 3 (Gemini)
- [ ] Typing indicators appear for each bot
- [ ] Mock responses arrive after 1.5-2.5s
- [ ] Messages display in correct chat bubbles
- [ ] User messages appear on right (purple gradient)
- [ ] Bot messages appear on left (blue gradient)

### Persistence
- [ ] Send multiple messages to all bots
- [ ] Refresh page (F5)
- [ ] All messages persist after refresh
- [ ] Scroll position maintained
- [ ] Session ID remains the same

### Selection Feature
- [ ] Click "Select as Preferred" on Bot 1
- [ ] Green checkmark appears on Bot 1
- [ ] Other bots show gray checkmarks
- [ ] Click "Select as Preferred" on Bot 2
- [ ] Selection switches to Bot 2
- [ ] Refresh page - selection persists

### Export Functionality
- [ ] Click "下載資料" button
- [ ] JSON file downloads successfully
- [ ] File named: `comparison_session_[sessionId]_[timestamp].json`
- [ ] Open JSON file - validate structure
- [ ] Check sessionId matches UI
- [ ] Check all messages present
- [ ] Check selection field correct

### Session Management
- [ ] Click "開始新對話" button
- [ ] Confirmation dialog appears
- [ ] Click "取消" - dialog closes, data preserved
- [ ] Click "開始新對話" again
- [ ] Click "確定"
- [ ] All chatbots cleared
- [ ] New session ID generated
- [ ] localStorage cleared

### Error Handling
- [ ] Error boundary doesn't trigger during normal use
- [ ] No console errors throughout testing

### Accessibility
- [ ] Tab through interface - focus indicators visible
- [ ] Press Enter in message input - message sends
- [ ] All buttons reachable via keyboard
- [ ] ARIA labels present (check inspector)

### Storage Monitoring
- [ ] Send many messages (50+)
- [ ] No quota warnings appear (normal usage)
- [ ] localStorage usage tracked properly

---

## Firefox Testing

### Basic Functionality
- [ ] Application loads without errors
- [ ] All UI elements render correctly
- [ ] Gradients display properly
- [ ] Font rendering correct

### Core Features
- [ ] Send messages to all 3 bots
- [ ] Messages persist after refresh
- [ ] Selection works correctly
- [ ] Export downloads JSON
- [ ] New session clears data

### localStorage
- [ ] localStorage persists across sessions
- [ ] No quota issues
- [ ] Data structure consistent

### Console
- [ ] No errors in console
- [ ] No warnings

---

## Safari Testing

### Basic Functionality
- [ ] Application loads without errors
- [ ] All UI elements render correctly
- [ ] Gradients display properly (Safari rendering)
- [ ] CSS grid layout works

### Core Features
- [ ] Send messages to all 3 bots
- [ ] Typing indicators work
- [ ] Messages persist after refresh
- [ ] Selection feature works
- [ ] Export downloads JSON
- [ ] New session clears data

### Safari-Specific
- [ ] LocalStorage works correctly
- [ ] No webkit-specific issues
- [ ] Touch targets appropriate size

### Console
- [ ] No errors in console
- [ ] No webkit warnings

---

## Edge Testing

### Basic Functionality
- [ ] Application loads without errors
- [ ] All UI elements render correctly
- [ ] Chromium rendering correct

### Core Features
- [ ] All messaging features work
- [ ] Persistence works
- [ ] Selection works
- [ ] Export works
- [ ] Session reset works

### Console
- [ ] No errors or warnings

---

## Cross-Browser Compatibility

### Layout Consistency
- [ ] UI layout identical across browsers
- [ ] Gradients render consistently
- [ ] Font sizes and spacing consistent

### Feature Parity
- [ ] All features work identically
- [ ] No browser-specific bugs
- [ ] Performance similar across browsers

---

## Mobile Responsive Testing (Optional)

### Chrome Mobile
- [ ] UI scales appropriately
- [ ] Touch targets large enough
- [ ] Scrolling smooth
- [ ] All features work on mobile

### Safari iOS
- [ ] UI renders correctly
- [ ] Touch interactions work
- [ ] localStorage persists

---

## Performance Testing

### Load Time
- [ ] Initial load <2 seconds
- [ ] No layout shift on load
- [ ] Smooth transitions

### Runtime Performance
- [ ] No lag when typing
- [ ] Smooth scrolling in chat
- [ ] Export completes quickly (<1s)

---

## Regression Testing

### Known Issues Verification
- [ ] No duplicate session IDs
- [ ] No localStorage corruption
- [ ] No React key warnings
- [ ] No hydration mismatches

---

## Final Checklist

- [ ] All Chrome tests passed
- [ ] All Firefox tests passed
- [ ] All Safari tests passed
- [ ] All Edge tests passed
- [ ] No console errors in any browser
- [ ] All features work consistently
- [ ] Performance acceptable
- [ ] Accessibility features work

---

## Notes

Record any issues found:

```
Issue 1: [Description]
Browser: [Chrome/Firefox/Safari/Edge]
Steps to reproduce:
1.
2.
3.

Expected:
Actual:
```

---

## Sign-Off

Tester: _______________
Date: _______________
Browsers Tested: [ ] Chrome [ ] Firefox [ ] Safari [ ] Edge
Status: [ ] PASS [ ] FAIL

Notes:
