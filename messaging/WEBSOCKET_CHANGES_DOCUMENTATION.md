# WebSocket System Changes - Frontend Documentation

## 🚨 BREAKING CHANGES - WebSocket API Update

**Date:** May 30, 2025  
**Version:** 2.0  
**Impact:** Major breaking changes to WebSocket endpoints and message handling

---

## 📋 Summary of Changes

### What Changed
We have completely restructured the WebSocket messaging system to handle **Group Messages** and **One-to-One Messages** through **separate WebSocket routes** with **dedicated handlers**.

### Why This Change
- **Better separation of concerns**: Group and one-to-one messages now have their own specialized handlers
- **Improved scalability**: Each message type can be optimized independently
- **Enhanced security**: More granular access control for different conversation types
- **Clearer message routing**: Frontend can connect to specific endpoints based on conversation type

---

## 🔄 Migration Guide

### BEFORE (Old System)
```javascript
// Single endpoint for all conversations
const websocket = new WebSocket(
    `ws://localhost:8000/ws/conversation/${conversationId}/?token=${accessToken}`
);
```

### AFTER (New System)
```javascript
// Separate endpoints based on conversation type

// For Group Conversations
const groupWebsocket = new WebSocket(
    `ws://localhost:8000/ws/group/${conversationId}/?token=${accessToken}`
);

// For One-to-One Conversations  
const oneToOneWebsocket = new WebSocket(
    `ws://localhost:8000/ws/one-to-one/${conversationId}/?token=${accessToken}`
);
```

---

## 🛣️ New WebSocket Routes

| Conversation Type | Old Endpoint | New Endpoint |
|------------------|--------------|--------------|
| **Group Chat** | `ws://localhost:8000/ws/conversation/{id}/` | `ws://localhost:8000/ws/group/{id}/` |
| **One-to-One Chat** | `ws://localhost:8000/ws/conversation/{id}/` | `ws://localhost:8000/ws/one-to-one/{id}/` |

---

## 📤 Message Format Changes

### New Message Response Format
All messages now include a `conversation_type` field to identify the message type:

```json
{
  "type": "message",
  "event": "new_message",
  "message": {
    "id": "4",
    "content": "Hello, this is a test message.",
    "sender_id": "1",
    "sender_name": "siazizextra",
    "conversation_id": "2",
    "timestamp": "2025-05-30T11:39:30.900633+00:00",
    "message_type": "text",
    "media_url": null,
    "metadata": {},
    "conversation_type": "group"  // ← NEW FIELD
  }
}
```

### Supported Message Types (Unchanged)
The message types you can send remain the same:

#### 1. Send Message
```json
{
  "type": "message",
  "content": "Hello, this is a test message.",
  "message_type": "text",
  "metadata": {}
}
```

#### 2. Typing Indicator
```json
{
  "type": "typing",
  "is_typing": true
}
```

#### 3. Read Receipt
```json
{
  "type": "read",
  "message_id": "5"
}
```

#### 4. Add/Remove Reaction
```json
{
  "type": "reaction",
  "message_id": "5",
  "reaction": "like",
  "action": "add"  // or "remove"
}
```

---

## 🔧 Frontend Implementation Guide

### Step 1: Determine Conversation Type
Before establishing a WebSocket connection, you need to determine if the conversation is a group or one-to-one chat.

```javascript
// Example API call to get conversation details
const getConversationType = async (conversationId) => {
  const response = await fetch(`/api/conversations/${conversationId}/`);
  const conversation = await response.json();
  return conversation.type; // returns "group" or "one_to_one"
};
```

### Step 2: Connect to Appropriate Endpoint
```javascript
const connectToChat = async (conversationId, accessToken) => {
  const conversationType = await getConversationType(conversationId);
  
  let websocketUrl;
  if (conversationType === 'group') {
    websocketUrl = `ws://localhost:8000/ws/group/${conversationId}/?token=${accessToken}`;
  } else if (conversationType === 'one_to_one') {
    websocketUrl = `ws://localhost:8000/ws/one-to-one/${conversationId}/?token=${accessToken}`;
  }
  
  const websocket = new WebSocket(websocketUrl);
  return websocket;
};
```

### Step 3: Handle Messages (Same as Before)
The message handling logic remains the same:

```javascript
websocket.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.type) {
    case 'message':
      handleNewMessage(data.message);
      break;
    case 'typing':
      handleTypingIndicator(data);
      break;
    case 'read_receipt':
      handleReadReceipt(data);
      break;
    case 'reaction':
      handleReaction(data);
      break;
    case 'presence':
      handlePresence(data);
      break;
    case 'heartbeat':
      // Connection is alive
      break;
  }
};
```

---

## 🔐 Authentication (Unchanged)

Authentication method remains the same:
- Pass JWT access token as query parameter: `?token=${accessToken}`
- Token must be valid and not expired
- User must be a participant in the conversation

---

## 🐛 Error Handling

### Common Error Responses
- **403 Forbidden**: Invalid token or user not authorized for this conversation
- **404 Not Found**: Conversation does not exist
- **Connection Refused**: Server is down or endpoint is incorrect

### Error Handling Example
```javascript
websocket.onerror = (error) => {
  console.error('WebSocket error:', error);
  // Handle reconnection logic
};

websocket.onclose = (event) => {
  if (event.code === 1006) {
    // Connection was closed abnormally
    console.log('Connection lost, attempting to reconnect...');
    // Implement reconnection logic
  }
};
```

---

## 🧪 Testing Examples

### Group Chat Test
```bash
# Terminal 1 (User 1)
wscat -c "ws://localhost:8000/ws/group/2/?token=USER1_TOKEN"

# Terminal 2 (User 2)  
wscat -c "ws://localhost:8000/ws/group/2/?token=USER2_TOKEN"

# Send message from Terminal 1:
{"type": "message","content": "Hello group!","message_type": "text","metadata": {}}
```

### One-to-One Chat Test
```bash
# Terminal 1 (User 1)
wscat -c "ws://localhost:8000/ws/one-to-one/1/?token=USER1_TOKEN"

# Terminal 2 (User 2)
wscat -c "ws://localhost:8000/ws/one-to-one/1/?token=USER2_TOKEN"

# Send message from Terminal 1:
{"type": "message","content": "Hello there!","message_type": "text","metadata": {}}
```

---

## ⚠️ Important Notes for Frontend Team

### 1. **Breaking Change**: Update All WebSocket Connections
- Replace all existing `ws://localhost:8000/ws/conversation/` URLs
- Use the new conversation-type-specific endpoints

### 2. **New Message Field**: Handle `conversation_type`
- All incoming messages now include `conversation_type: "group"` or `conversation_type: "one_to_one"`
- Use this field for UI differentiation if needed

### 3. **Connection Management**
- Each conversation type has its own consumer with optimized handling
- Group messages use `group_{conversation_id}` channel groups
- One-to-one messages use `one_to_one_{conversation_id}` channel groups

### 4. **Backward Compatibility**
- The old `/ws/conversation/` endpoint is **deprecated** and will be removed in future versions
- **Immediate migration required**

---

## 🚀 Benefits of New System

1. **Better Performance**: Specialized handlers for each conversation type
2. **Improved Security**: More granular access control
3. **Enhanced Debugging**: Easier to trace group vs one-to-one message flows
4. **Future-Proof**: Easier to add conversation-type-specific features
5. **Cleaner Architecture**: Separation of concerns between message types

---

## 📞 Support

If you encounter any issues during migration:
1. Check that you're using the correct WebSocket endpoint for the conversation type
2. Verify that your JWT tokens are valid and not expired
3. Ensure the user is a participant in the conversation
4. Check server logs for detailed error information

**Backend Team Contact**: [Your contact information]
**Documentation Date**: May 30, 2025
**Next Review**: June 15, 2025
