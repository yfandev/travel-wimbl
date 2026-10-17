"""Shared Brain. Agents call get_inherited_lessons() before working and propose_lesson() after."""
from wimbl.memory.journal import SCOPES, SharedMemory
from wimbl.memory.lessons import Lesson, LessonProposal, influence
from wimbl.memory.store import (InheritedLessons, LessonStore, ProposalResult, default_store, get_inherited_lessons,
                                propose_lesson)

__all__ = ["SCOPES", "SharedMemory", "Lesson", "LessonProposal", "influence", "InheritedLessons", "LessonStore",
           "ProposalResult", "default_store", "get_inherited_lessons", "propose_lesson"]
