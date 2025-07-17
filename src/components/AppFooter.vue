<template>
  <div class="position-fixed bottom-0 end-0 me-3 mb-3" style="width: 400px; z-index: 1050;">
    <div class="card border-0 shadow">
      <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center" @click="toggleChat" style="cursor: pointer;">
        <div>
          <i class="bi bi-robot me-2"></i>
          <span>AI Assistant</span>
        </div>
        <i class="bi" :class="isChatOpen ? 'bi-chevron-down' : 'bi-chevron-up'"></i>
      </div>
      <div class="collapse" :class="{ show: isChatOpen }">
        <div class="card-body p-0">
          <div class="border-bottom" style="max-height: 600px; overflow-y: auto;" ref="chatContainer">
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
  </div>
</template>

<script>
import { marked } from 'marked';

export default {
  name: "AppFooter",
  data() {
    return {
      baseURL: process.env.VUE_APP_API_BASE,
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
    }
  },
  
  mounted() {
    this.resetSuggestions();
  },

  methods: {
    toggleChat() {
      this.isChatOpen = !this.isChatOpen;
    },

    // Use marked to convert markdown to HTML
    renderMarkdown(text) {
      if (text) {
        return marked.parse(text);
      }
      return "";
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

        // Check for server error response
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
                // const reasoning = parsed.reasoning_content || "";
                const content = parsed.content || "";

                // fullResponse += reasoning + content;
                fullResponse += content;

                // Update the bot message
                if (botIndex !== -1) {
                  if (fullResponse) {
                    this.messages[botIndex].text = fullResponse;
                  } else {
                    this.messages[botIndex].text = "*Thinking...*";
                  }
                }

                this.$nextTick(() => {
                  const container = this.$refs.chatContainer;
                  if (container) {
                    container.scrollTop = container.scrollHeight;
                  }
                });
              } catch (err) {
                console.error("Failed to parse stream JSON:", err, jsonStr);
              }
            }
          }
        }

        // Mark streaming as complete
        const botMessageIndex = this.messages.findIndex(msg => msg.id === botMessage.id);
        if (botMessageIndex !== -1) {
          this.messages[botMessageIndex].streaming = false;
        }
        
      } catch (error) {
        console.error('Error calling OpenAI API:', error);
        
        // Add error message
        this.messages.push({
          id: Date.now() + 2,
          text: "Sorry, I encountered an error. Please try again.",
          type: "bot",
        });
      } finally {
        this.isLoading = false;
        
        // Auto-scroll to bottom
        this.$nextTick(() => {
          const container = this.$refs.chatContainer;
          if (container) {
            container.scrollTop = container.scrollHeight;
          }
        });
      }
    },

    selectSuggestion(question) {
      this.currentMessage = question;
      this.sendMessage();
      // Remove this question from the suggestions array
      this.suggestedQuestions = this.suggestedQuestions.filter(q => q !== question);
      if (this.suggestedQuestions.length === 0) {
        this.showSuggestions = false;
      }
    },
    
    // Reset the suggestions to the original preset questions
    resetSuggestions() {
      // Reset to original suggestions when needed
      this.suggestedQuestions = this.presetQuestions;
      this.showSuggestions = true;
    }
  }
}
</script>