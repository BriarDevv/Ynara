// Re-export desde @ynara/core (ADR-012): constantes y copy canned del chat,
// compartidos con mobile. Se mantiene `@/features/chat/constants` (y los
// `../constants` relativos) como superficie estable.
export {
  AGENT_MODES,
  cannedActions,
  cannedReply,
  isAgentMode,
  MODE_INTRO,
} from "@ynara/core/features/chat";
