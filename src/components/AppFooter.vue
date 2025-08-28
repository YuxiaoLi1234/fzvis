<template>
  <footer class="footer fixed-bottom bg-white border-top shadow-sm">
    <div class="container-fluid px-3 py-2 d-flex align-items-center gap-3">
      <!-- History button -->
      <button class="btn btn-sm btn-outline-secondary d-flex align-items-center" @click="toggleHistory">
        <i class="bi bi-clock-history me-2"></i>
        History
        <span v-if="history.length" class="badge bg-secondary ms-2">{{ history.length }}</span>
      </button>

      <!-- Status (center) -->
      <div class="flex-grow-1 text-center d-flex justify-content-center align-items-center gap-2">
        <template v-if="progress.active">
          <div class="flex-grow-1 d-flex align-items-center gap-2" style="max-width: 720px;">
            <div class="progress flex-shrink-0" style="height: 6px; width: 60%; min-width: 120px;">
              <div class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" :style="{ width: (progress.percent || 0) + '%' }" aria-valuemin="0" aria-valuemax="100"></div>
            </div>
            <small class="text-muted text-truncate" style="max-width: 40%" :title="progress.message">{{ progress.message || ('Working… ' + (progress.percent || 0) + '%') }}</small>
          </div>
        </template>
        <template v-else>
          <i class="bi" :class="statusIconClass"></i>
          <span :class="statusClass">{{ status.message }}</span>
        </template>
      </div>

      <!-- AI Assistant button (right) -->
      <button class="btn btn-sm btn-primary" @click="toggleChat">
        <i class="bi bi-robot me-1"></i> Assistant
      </button>
    </div>

    <!-- Floating Chat Panel -->
    <div class="position-fixed bottom-0 end-0 me-3 mb-5" style="width: 420px; z-index: 1050;" v-if="isChatOpen">
      <div class="card border-0 shadow">
        <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center" style="cursor: pointer;" @click="toggleChat">
          <div>
            <i class="bi bi-robot me-2"></i>
            <span>AI Assistant</span>
          </div>
          <i class="bi bi-x"></i>
        </div>
        <div class="card-body p-0">
          <div class="border-bottom" style="max-height: 60vh; overflow-y: auto;" ref="chatContainer">
            <div class="p-3">
              <div v-for="message in messages" :key="message.id" class="mb-2">
                <div class="d-flex" :class="message.type === 'user' ? 'justify-content-end' : 'justify-content-start'">
                  <div class="px-3 py-2 rounded" :class="message.type === 'user' ? 'bg-primary text-white' : 'bg-light'" style="max-width: 80%;">
                    <span v-if="message.type === 'bot'" v-html="renderMarkdown(message.text)"></span>
                    <span v-else>{{ message.text }}</span>
                  </div>
                </div>
              </div>

              <!-- Suggested Questions -->
              <div v-if="showSuggestions && !isLoading" class="mt-3 mb-2">
                <div class="d-flex flex-wrap gap-2">
                  <button 
                    v-for="(question, index) in suggestedQuestions" 
                    :key="index"
                    @click="selectSuggestion(question)"
                    class="btn btn-sm btn-outline-primary rounded-pill">
                    {{ question }}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div class="p-3">
            <div class="input-group">
              <input 
                v-model="currentMessage" 
                @keyup.enter="sendMessage"
                :disabled="isLoading"
                placeholder="Type your message..."
                class="form-control"
              />
              <button @click="sendMessage" :disabled="isLoading || !currentMessage.trim()" class="btn btn-primary">
                <i class="bi bi-send"></i>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- History Panel (popover-like) -->
    <div v-if="showHistory" class="position-fixed bottom-0 start-0 ms-3 mb-5" style="width: 520px; max-width: 60vw; z-index: 1050;">
      <div class="card border-0 shadow">
        <div class="card-header d-flex justify-content-between align-items-center">
          <div>
            <i class="bi bi-clock-history me-2"></i>
            <span>Operation History</span>
          </div>
          <div class="btn-group">
            <button type="button" class="btn btn-sm btn-outline-secondary" @click="clearHistory" :disabled="history.length === 0" title="Clear">
              <i class="bi bi-trash"></i>
            </button>
            <button type="button" class="btn btn-sm btn-outline-secondary" @click="toggleHistory" title="Close">
              <i class="bi bi-x-lg"></i>
            </button>
          </div>
        </div>
        <div class="card-body p-0" style="max-height: 50vh; overflow: auto;">
          <div v-if="history.length === 0" class="p-4 text-muted text-center">No operations yet.</div>
          <ul v-else class="list-group list-group-flush">
            <li v-for="(item, idx) in orderedHistory" :key="idx" class="list-group-item d-flex justify-content-between align-items-start">
              <div class="me-3">
                <span class="badge rounded-pill text-bg-light border me-2 text-capitalize">{{ item.kind }}</span>
                <span>{{ item.text }}</span>
              </div>
              <small class="text-muted">{{ formatTime(item.timestamp) }}</small>
            </li>
          </ul>
        </div>
      </div>
    </div>
  </footer>
</template>

<script>
import { marked } from 'marked';

export default {
  name: "AppFooter",
  data() {
    return {
      baseURL: localStorage.getItem("fzvis_server_address"),
      isChatOpen: false,
      isLoading: false,
      currentMessage: "",
      messages: [
        { id: 1, text: "Hello! How can I help you?", type: "bot" }
      ],
      showSuggestions: true,
      presetQuestions: [
        "What is the pipeline of SZ3 compressor?",
        "Explain the differences between SZ and SZ3.",
        "How does the ZFP compressor work?",
        "What are aboslute and relative error bound?",
      ],
      suggestedQuestions: [],
      showHistory: false,
    }
  },
  computed: {
    status() {
      return this.$store.state.status;
    },
    history() {
      return this.$store.state.history;
    },
    progress() {
      return this.$store.state.progress || { active: false, percent: 0, message: '' };
    },
    statusClass() {
      const map = {
        success: 'text-success',
        info: 'text-info',
        warning: 'text-warning',
        danger: 'text-danger',
        secondary: 'text-muted'
      };
      return map[this.status.type] || 'text-muted';
    },
    statusIconClass() {
      const map = {
        success: 'bi-check-circle text-success',
        info: 'bi-info-circle text-info',
        warning: 'bi-exclamation-triangle text-warning',
        danger: 'bi-x-circle text-danger',
        secondary: 'bi-dot text-muted'
      };
      return map[this.status.type] || 'bi-dot text-muted';
    },
    orderedHistory() {
      return [...this.history].sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0));
    }
  },
  mounted() {
    this.resetSuggestions();
  },
  methods: {
    toggleChat() {
      this.isChatOpen = !this.isChatOpen;
    },
    toggleHistory() {
      this.showHistory = !this.showHistory;
    },
    clearHistory() {
      this.$store.commit('clearHistory');
    },
    // helpers
    renderMarkdown(text) {
      if (text) return marked.parse(text);
      return "";
    },
    scrollHistoryToEnd() {
      const el = this.$refs.historyContainer;
      if (el) el.scrollLeft = el.scrollWidth;
    },
    formatTime(ts) {
      const d = new Date(ts || Date.now());
      return d.toLocaleTimeString();
    },

    async sendMessage() {
      if (!this.currentMessage.trim() || this.isLoading) return;

      const userMessage = {
        id: Date.now(),
        text: this.currentMessage,
        type: "user"
      };
      this.messages.push(userMessage);

      const messageToSend = this.currentMessage;
      this.currentMessage = "";
      this.isLoading = true;

      try {
        // Create bot message for streaming
        const botMessage = {
          id: Date.now() + 1,
          text: "",
          type: "bot",
          streaming: true,
        };
        this.messages.push(botMessage);
        
        const response = await fetch(`${this.baseURL}/chat`, {
          method: "POST",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
          },
          body: new URLSearchParams({ message: messageToSend }),
        });

        if (!response.ok) {
          let errorText = "Unknown error";
          try {
            const errorData = await response.json();
            errorText = errorData.error || JSON.stringify(errorData);
          } catch (e) {
            errorText = await response.text();
          }
          this.messages.push({
            id: Date.now() + 2,
            text: `Sorry, server error: ${errorText}`,
            type: "bot",
          });
          return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");

        let fullResponse = "";
        const botIndex = this.messages.findIndex(msg => msg.id === botMessage.id);
        // eslint-disable-next-line no-constant-condition
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split("\n").filter(line => line.trim() !== "");

          for (const line of lines) {
            if (line.startsWith("data:")) {
              const jsonStr = line.replace(/^data:\s*/, "");
              if (jsonStr === "[DONE]") break;

              try {
                const parsed = JSON.parse(jsonStr);
                const content = parsed.content || "";
                fullResponse += content;

                if (botIndex !== -1) {
                  this.messages[botIndex].text = fullResponse || "*Thinking...*";
                }

                this.$nextTick(() => {
                  const container = this.$refs.chatContainer;
                  if (container) container.scrollTop = container.scrollHeight;
                });
              } catch (err) {
                console.error("Failed to parse stream JSON:", err, jsonStr);
              }
            }
          }
        }

        const botMessageIndex = this.messages.findIndex(msg => msg.id === botMessage.id);
        if (botMessageIndex !== -1) this.messages[botMessageIndex].streaming = false;
        
      } catch (error) {
        console.error('Error calling OpenAI API:', error);
        this.messages.push({ id: Date.now() + 2, text: "Sorry, I encountered an error. Please try again.", type: "bot" });
      } finally {
        this.isLoading = false;
        this.$nextTick(() => {
          const container = this.$refs.chatContainer;
          if (container) container.scrollTop = container.scrollHeight;
        });
      }
    },

    selectSuggestion(question) {
      this.currentMessage = question;
      this.sendMessage();
      this.suggestedQuestions = this.suggestedQuestions.filter(q => q !== question);
      if (this.suggestedQuestions.length === 0) this.showSuggestions = false;
    },
    resetSuggestions() {
      this.suggestedQuestions = this.presetQuestions;
      this.showSuggestions = true;
    }
  }
}
</script>

<style scoped>
/* Remove scroller; no longer used */
.history-scroller { display: none; }
</style>