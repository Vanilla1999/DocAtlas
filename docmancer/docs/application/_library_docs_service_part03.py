"""LibraryDocsApplicationService implementation shard 3."""
from __future__ import annotations

from ._library_docs_service_shared import *  # noqa: F401,F403


class _LibraryDocsApplicationServicePart03:
    def get_docs(
        self,
        library: str,
        topic: str | None = None,
        tokens: int | None = None,
        ecosystem: str | None = None,
        version: str | None = None,
        docs_url: str | None = None,
        docs_url_template: str | None = None,
        source_type: str | None = None,
        force_refresh: bool = False,
        project_path: str | None = None,
        response_style: str | None = None,
        library_requirement_contract: dict[str, list[str]] | None = None,
    ) -> DocsResult:
        response_style = validate_response_style(response_style)
        if hasattr(self.facade, "_library_get_docs_impl"):
            hook_kwargs = {
                "topic": topic,
                "tokens": tokens,
                "ecosystem": ecosystem,
                "version": version,
                "docs_url": docs_url,
                "docs_url_template": docs_url_template,
                "source_type": source_type,
                "force_refresh": force_refresh,
                "project_path": project_path,
                "response_style": response_style,
            }
            if library_requirement_contract is not None:
                hook_kwargs["library_requirement_contract"] = library_requirement_contract
            return self.facade._library_get_docs_impl(
                library,
                **hook_kwargs,
            )
        input_args = {
            "library": library,
            "topic": topic,
            "tokens": tokens,
            "ecosystem": ecosystem,
            "version": version,
            "source_type": source_type,
            "docs_url": docs_url,
            "docs_url_template": docs_url_template,
            "force_refresh": force_refresh,
            "project_path": project_path,
        }
        input_docs_url = docs_url
        input_docs_url_template = docs_url_template
        project_warnings: list[str] = []
        requested_version = version
        version_source = "explicit" if version is not None else None
        docs_snapshot_exact: bool | None = None
        docs_binding_source: str | None = None
        exact_version_resolution = None  # Will be set if exact-version logic triggers
        if version is None and project_path:
            project_version, project_docs_url, project_template, project_warnings, requested_version, docs_snapshot_exact, project_version_source, docs_binding_source = self._project_version_for(
                library=library,
                ecosystem=ecosystem,
                project_path=project_path,
            )
            if project_version:
                version = project_version
                version_source = project_version_source or "project"
                docs_url = docs_url or project_docs_url
                docs_url_template = docs_url_template or project_template
        elif version is not None and ecosystem == "pub":
            docs_snapshot_exact = True
            docs_binding_source = "pub_dartdoc" if docs_url or docs_url_template else None
        elif version is not None and ecosystem == "rust":
            docs_snapshot_exact = True
            docs_binding_source = "docs_rs" if docs_url or docs_url_template else None
        if ecosystem is None and self._is_flutter_library(library):
            ecosystem = "flutter"

        resolution = self._resolve_docs_source(
            library,
            ecosystem,
            version,
            docs_url,
            docs_url_template,
            source_type,
            input_docs_url=input_docs_url,
            input_docs_url_template=input_docs_url_template,
        )
        info = resolution.info
        docs_url_source = resolution.docs_url_source
        if info.status == "ambiguous":
            warnings = self._join_warnings("ambiguous_library", extra=project_warnings)
            return DocsResult(
                library_id="",
                library=library,
                version=version,
                topic=topic,
                refreshed=False,
                stale_before_refresh=True,
                warning=warnings,
                last_refreshed_at=None,
                results=[],
                warnings=[warnings] if warnings else [],
                requested_version=requested_version,
                resolved_version=version,
                version_source=version_source,
                docs_snapshot_exact=docs_snapshot_exact,
                docs_exactness=self._docs_exactness(docs_snapshot_exact, docs_url, docs_url_template),
                docs_binding_source=docs_binding_source,
                confidence="high" if version_source in {"explicit", "lockfile_exact", "manifest_exact"} else None,
                status="ambiguous",
                decision="choose_candidate",
                request=self._docs_request(input_args),
                identity=self._docs_identity(info),
                policy=self._docs_policy("ambiguous", has_registered_source=True),
                diagnostics={**resolution.diagnostics, "warnings": [{"code": "ambiguous_library", "blocking": True}]},
                next_actions=["Choose one candidate and retry get_library_docs with its arguments_patch."],
                candidates=info.candidates,
            )
        if info.status == "docs_url_conflict":
            warning = self._join_warnings("docs_url_conflict", extra=project_warnings)
            return DocsResult(
                library_id=info.library_id or "",
                library=info.library,
                version=info.version,
                topic=topic,
                refreshed=False,
                stale_before_refresh=info.stale,
                warning=warning,
                last_refreshed_at=info.last_refreshed_at,
                source_type=info.source_type,
                results=[],
                warnings=[warning] if warning else [],
                requested_version=requested_version if requested_version is not None else info.requested_version,
                resolved_version=info.resolved_version or info.version,
                version_source=version_source if version_source is not None else info.version_source,
                docs_snapshot_exact=docs_snapshot_exact if docs_snapshot_exact is not None else info.docs_snapshot_exact,
                docs_exactness=self._docs_exactness(info.docs_snapshot_exact, info.docs_url, info.docs_url_template),
                docs_binding_source=docs_binding_source or "registry",
                confidence=info.version_confidence,
                status="needs_input",
                decision="retry_same_tool",
                request=self._docs_request(input_args, info),
                identity=self._docs_identity(info, docs_url_source="registry"),
                policy=self._docs_policy("needs_input", has_registered_source=True),
                diagnostics={**resolution.diagnostics, "warnings": [{"code": "docs_url_conflict", "blocking": True}]},
                next_actions=["Retry get_library_docs without docs_url to use the registered source, or explicitly refresh/re-register the docs target."],
            )
        if info.library_id is None:
            # Check exact-version resolver for Python libraries without registered source
            exact_version_resolution = None
            if ecosystem == "python" and version is not None and version not in ("latest", "*", "") and not docs_url:
                from docmancer.docs.exact_version import resolve_python_versioned_docs
                normalized_lib = library.lower().replace("-", "_").replace(" ", "_")
                exact_version_resolution = resolve_python_versioned_docs(normalized_lib, version)

                if exact_version_resolution and exact_version_resolution.status == "exact_version_not_supported":
                    # Return structured unsupported response without silent fallback
                    return DocsResult(
                        library_id="",
                        library=library,
                        version=version,
                        topic=topic,
                        refreshed=False,
                        stale_before_refresh=False,
                        warning=f"Exact version {version} not supported: {exact_version_resolution.reason_code}",
                        last_refreshed_at=None,
                        source_type=source_type,
                        results=[],
                        warnings=[f"exact_version_not_supported: {exact_version_resolution.reason_code}"],
                        requested_version=version,
                        resolved_version=None,
                        version_source=version_source,
                        docs_snapshot_exact=False,
                        docs_exactness="exact_version_not_supported",
                        docs_binding_source=None,
                        confidence="high",
                        status="exact_version_not_supported",
                        decision="stop",
                        request=self._docs_request(input_args),
                        identity=self._docs_identity(None),
                        policy=self._docs_policy("exact_version_not_supported", has_registered_source=False),
                        diagnostics={
                            "exact_version": {
                                "expected": version,
                                "used": None,
                                "match": None,
                                "status": exact_version_resolution.status,
                                "fallback": False,
                                "reason_code": exact_version_resolution.reason_code,
                                "fallback_available": exact_version_resolution.fallback_docs_url is not None,
                                "fallback_docs_url": exact_version_resolution.fallback_docs_url,
                            }
                        },
                        next_actions=[
                            "Retry without version to use latest docs, or use fallback_docs_url if available."
                        ],
                    )

            warning = self._join_warnings("library_docs_source_required", extra=project_warnings)
            warnings = [warning] if warning else []
            candidates = info.candidates
            source_options = library_docs_source_options(library, ecosystem, version, source_type, candidates)
            arguments_patch = dict(candidates[0].get("arguments_patch") or {}) if candidates else {}
            if candidates and candidates[0].get("docs_url"):
                arguments_patch.setdefault("docs_url", candidates[0]["docs_url"])
            if candidates and candidates[0].get("source_type"):
                arguments_patch.setdefault("source_type", candidates[0]["source_type"])
            if candidates and candidates[0].get("ecosystem"):
                arguments_patch.setdefault("ecosystem", candidates[0]["ecosystem"])
            next_actions_list = library_docs_source_next_actions(library, ecosystem, version, source_type, candidates, source_options)
            return DocsResult(
                library_id="",
                library=library,
                version=version,
                topic=topic,
                refreshed=False,
                stale_before_refresh=True,
                warning=warning,
                last_refreshed_at=None,
                results=[],
                warnings=warnings,
                requested_version=requested_version,
                resolved_version=version,
                version_source=version_source,
                docs_snapshot_exact=docs_snapshot_exact,
                docs_exactness=self._docs_exactness(docs_snapshot_exact, docs_url, docs_url_template),
                docs_binding_source=docs_binding_source,
                confidence="high" if version_source in {"explicit", "lockfile_exact", "manifest_exact"} else None,
                status="needs_input",
                decision="retry_same_tool",
                reason_code="library_docs_source_required",
                message="Documentation source is not registered locally. Ask the user which library documentation to use; if they do not know, use best-effort web discovery with quality not guaranteed.",
                requires_confirmation=True,
                arguments_patch=arguments_patch or None,
                request=self._docs_request(input_args),
                identity=self._docs_identity(info),
                policy=self._docs_policy("needs_input", has_registered_source=resolution.has_registered_source),
                diagnostics=source_required_diagnostics({
                    **resolution.diagnostics,
                    "warnings": [{"code": "library_docs_source_required", "blocking": True}],
                    "question": f"Which documentation source should be used for {library}?",
                    "source_options": source_options,
                    "discovery_candidates": candidates,
                    "quality_warning": "Best-effort web discovery may choose an incomplete or unofficial documentation source; prefer an explicit docs_url.",
                }),
                next_actions=next_actions_list,
                candidates=candidates,
                discovery_candidates=candidates,
            )

        requested_version = requested_version if requested_version is not None else info.requested_version
        version_source = version_source if version_source is not None else info.version_source
        docs_snapshot_exact = docs_snapshot_exact if docs_snapshot_exact is not None else info.docs_snapshot_exact
        docs_binding_source = docs_binding_source or ("registry" if info.docs_url or info.docs_url_template else None)
        docs_exactness = self._docs_exactness(docs_snapshot_exact, info.docs_url, info.docs_url_template)
        confidence = info.version_confidence or ("high" if version_source in {"explicit", "lockfile_exact", "manifest_exact"} else None)
        if info.library_id and (
            requested_version != info.requested_version
            or version_source != info.version_source
            or docs_snapshot_exact != info.docs_snapshot_exact
        ):
            updated_record = self.registry.upsert(
                library=info.library,
                ecosystem=info.ecosystem,
                version=info.version,
                docs_url=info.docs_url,
                docs_url_template=info.docs_url_template,
                source_type=info.source_type,
                now=self._now(),
                status=info.status,
                last_refreshed_at=info.last_refreshed_at,
                requested_version=requested_version,
                resolved_version=info.resolved_version or info.version,
                version_source=version_source,
                version_confidence=confidence,
                version_inferred=version_source != "explicit",
                docs_snapshot_exact=docs_snapshot_exact,
            )
            info = self.resolve_library(updated_record.library_id, source_type=updated_record.source_type)

        stale_before = info.stale
        refreshed = False
        warning = None
        if version is None and info.version == "latest":
            warning = "No version was provided; using latest/default docs."
        if project_warnings:
            warning = self._join_warnings(warning, extra=project_warnings)
        warnings = [warning] if warning else []
        diagnostic_warnings: list[dict[str, Any]] = []
        if docs_url_source == "registry":
            diagnostic_warnings.append({"code": "used_registry_docs_url", "blocking": False})
        if warning:
            diagnostic_warnings.append({"code": warning, "blocking": False})
        if info.status == "failed" and not force_refresh:
            failed_warning = info.message or "registered documentation source is marked failed"
            diagnostic_warnings.append({"code": "registered_source_failed", "blocking": True, "message": failed_warning})
            return DocsResult(
                library_id=info.library_id,
                library=info.library,
                version=info.version,
                topic=topic,
                refreshed=False,
                stale_before_refresh=stale_before,
                warning=failed_warning,
                last_refreshed_at=info.last_refreshed_at,
                source_type=info.source_type,
                results=[],
                warnings=[failed_warning],
                requested_version=requested_version,
                resolved_version=info.resolved_version or info.version,
                version_source=version_source,
                docs_snapshot_exact=docs_snapshot_exact,
                docs_exactness=docs_exactness,
                docs_binding_source=docs_binding_source,
                confidence=confidence,
                status="error",
                decision="stop",
                reason_code="registered_source_failed",
                message="Registered documentation source is failed; refusing automatic refresh during get_library_docs to avoid long MCP timeouts.",
                request=self._docs_request(input_args, info),
                identity=self._docs_identity(info, docs_url_source=docs_url_source),
                policy=self._docs_policy("error", has_registered_source=True),
                diagnostics=self._with_dart_diagnostics(
                    {**resolution.diagnostics, "reason_code": "registered_source_failed", "warnings": diagnostic_warnings},
                    info=info,
                    reason_code="registered_source_failed",
                    pages_discovered=info.pages,
                    pages_extracted=0,
                    chunks_created=0,
                ),
                next_actions=[
                    {"tool": "refresh_library_docs", "requires_confirmation": True, "arguments_patch": {"library": info.library, "ecosystem": info.ecosystem, "version": info.version, "force": True}, "reason": "Refresh the failed docs target explicitly after confirming network/indexing cost."}
                ],
            )

        if force_refresh or stale_before:
            result = self.refresh_docs(
                info.library_id,
                ecosystem=None,
                docs_url=info.docs_url,
                docs_url_template=info.docs_url_template,
                source_type=info.source_type,
                force=force_refresh,
            )
            refreshed = result.status == "updated"
            if result.status in {"failed", "needs_docs_url"}:
                warning = result.status if not result.message else f"{result.status}: {result.message}"
                warnings = [warning]
                if not info.local:
                    return DocsResult(
                        info.library_id,
                        info.library,
                        info.version,
                        topic,
                        False,
                        stale_before,
                        warning,
                        None,
                        source_type=info.source_type,
                        results=[],
                        warnings=warnings,
                        requested_version=requested_version,
                        resolved_version=info.version,
                        version_source=version_source,
                        docs_snapshot_exact=docs_snapshot_exact,
                        docs_exactness=docs_exactness,
                        docs_binding_source=docs_binding_source,
                        confidence=confidence,
                        status="error",
                        decision="stop",
                        request=self._docs_request(input_args, info),
                        identity=self._docs_identity(info, docs_url_source=docs_url_source),
                        policy=self._docs_policy("error", has_registered_source=True),
                        diagnostics={**resolution.diagnostics, **((result.preindex or {}) if result.preindex else {}), "warnings": diagnostic_warnings},
                        next_actions=["Retry get_library_docs with force_refresh=false if local docs are usable, or refresh/register the source again."],
                    )
                if stale_before:
                    stale_warning = _stale_docs_warning(info.last_refreshed_at, self.stale_after_days)
                    warnings = [*warnings, stale_warning]
                    diagnostic_warnings.append({"code": "stale_docs_used", "blocking": False})

        latest = self.resolve_library(info.library_id, source_type=info.source_type)
        record = self.registry.get(info.library_id, source_type=info.source_type)
        if record is None:
            return DocsResult(
                info.library_id,
                info.library,
                info.version,
                topic,
                refreshed,
                stale_before,
                warning,
                latest.last_refreshed_at,
                source_type=info.source_type,
                results=[],
                warnings=warnings,
                requested_version=requested_version,
                resolved_version=info.version,
                version_source=version_source,
                docs_snapshot_exact=docs_snapshot_exact,
                docs_exactness=docs_exactness,
                docs_binding_source=docs_binding_source,
                confidence=confidence,
                status="success",
                decision="answer_returned",
                request=self._docs_request(input_args, info),
                identity=self._docs_identity(info, docs_url_source=docs_url_source),
                policy=self._docs_policy("success", has_registered_source=True),
                diagnostics={**resolution.diagnostics, "warnings": diagnostic_warnings},
            )
        pages, chunks = self.registry_ops.count_index_entries(record)
        index_db_exists = Path(self._index_config_for(record).index.db_path).exists()
        if self._index_size_for(record) == 0 or (pages == 0 and chunks == 0 and index_db_exists):
            return self._empty_library_index_result(
                info=info,
                latest=latest,
                topic=topic,
                refreshed=refreshed,
                stale_before=stale_before,
                warning=warning,
                warnings=warnings,
                requested_version=requested_version,
                version_source=version_source,
                docs_snapshot_exact=docs_snapshot_exact,
                docs_exactness=docs_exactness,
                docs_binding_source=docs_binding_source,
                confidence=confidence,
                input_args=input_args,
                docs_url_source=docs_url_source,
                diagnostics=resolution.diagnostics,
                diagnostic_warnings=diagnostic_warnings,
            )
        query = topic.strip() if topic else info.library
        retrieval_filters = {"library_id": record.library_id}
        resolved_version = record.resolved_version or record.version
        # The index deliberately normalizes the floating ``latest`` version to
        # an empty promoted field.  Its canonical library ID still contains the
        # version and source identity, so applying that unrepresentable filter
        # would hide the same isolated corpus immediately after refresh.
        if resolved_version and resolved_version.casefold() != "latest":
            retrieval_filters["resolved_version"] = resolved_version
        if record.docs_snapshot_exact is True:
            retrieval_filters["exact_snapshot_required"] = True
        requirements = build_requirements(
            query,
            exact_version=resolved_version,
            profile="library_docs_answer",
            library_requirement_contract=library_requirement_contract,
        )
        explicit_query_values, has_unqualified_explicit_query_list = (
            _explicit_library_query_analysis(query)
        )
        existing_requirement_values = {
            requirement.value.casefold() for requirement in requirements
        }
        missing_explicit_values = [
            value for value in explicit_query_values
            if value.casefold() not in existing_requirement_values
        ]
        if missing_explicit_values:
            requirements = build_requirements(
                query,
                public_requirements=missing_explicit_values,
                exact_version=resolved_version,
                profile="library_docs_answer",
                library_requirement_contract=library_requirement_contract,
            )
        dispatch_result = self.facade.agent_gateway.query_library(
            record,
            query,
            budget=tokens or DEFAULT_DOC_TOKENS,
            filters=retrieval_filters,
            requirements=requirements,
        )
        chunks = getattr(dispatch_result, "chunks", dispatch_result)
        if has_unqualified_explicit_query_list:
            chunks = []
            diagnostic_warnings.append({
                "code": "unqualified_explicit_query_list",
                "blocking": True,
            })
        retrieval_diagnostics = {
            "requested": {
                "mode": str(
                    getattr(self.config.retrieval, "default_mode", "lexical") or "lexical"
                ).lower(),
                "raw_topic_sha256": hashlib.sha256(query.encode()).hexdigest(),
                "filters": retrieval_filters,
                "record": {
                    "library_id": record.library_id,
                    "canonical_id": record.canonical_id,
                    "resolved_version": resolved_version,
                    "docs_snapshot_exact": record.docs_snapshot_exact,
                },
            },
            "used": {
                "mode": getattr(dispatch_result, "mode_used", "legacy_agent_query"),
                "candidate_counts": getattr(dispatch_result, "candidate_counts", {"legacy": len(chunks)}),
                "failures": getattr(dispatch_result, "failures", {}),
                "query_plan_hash": getattr(dispatch_result, "query_plan_hash", ""),
                "component_ranks": {},
            },
        }
        allowed_ids = {info.library_id}
        if info.version:
            allowed_ids.add(legacy_library_id(info.library, info.version))
        expected_roots = self._expected_docset_roots(info, record)
        chunks_before_guard = list(chunks)
        filtered_chunks = []
        rejection_counts: dict[str, int] = {}
        for chunk in chunks_before_guard:
            reason = self._library_chunk_rejection_reason(chunk, info, allowed_ids, expected_roots)
            if reason is None:
                filtered_chunks.append(chunk)
            else:
                rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
        chunks = filtered_chunks
        dropped = len(chunks_before_guard) - len(chunks)
        if dropped:
            diagnostic_warnings.append({"code": "cross_source_contamination_filtered", "blocking": False, "dropped": dropped})
            for code, count in sorted(rejection_counts.items()):
                diagnostic_warnings.append({"code": code, "blocking": False, "dropped": count})
        chunks_before_low_value_guard = list(chunks)
        chunks = [chunk for chunk in chunks_before_low_value_guard if not _drop_low_value_library_section(chunk.text, (chunk.metadata or {}).get("title"))]
        retrieval_diagnostics["used"]["component_ranks"] = {
            str((chunk.metadata or {}).get("section_id") or index):
            dict(((chunk.metadata or {}).get("retrieval_trace") or {}).get("component_ranks") or {})
            for index, chunk in enumerate(chunks, start=1)
        }
        retrieval_diagnostics["post_guard"] = {
            "before": len(chunks_before_guard),
            "accepted": len(filtered_chunks),
            "rejected": rejection_counts,
            "low_value_dropped": len(chunks_before_low_value_guard) - len(chunks),
        }
        if not chunks:
            reason_code = (
                "unqualified_explicit_query_list"
                if has_unqualified_explicit_query_list
                else "guard_dropped_all" if dropped > 0
                else "no_library_docs_results"
            )
            reason_diagnostics = {**resolution.diagnostics, "retrieval": retrieval_diagnostics, "reason_code": reason_code, "warnings": diagnostic_warnings}
            reason_diagnostics = self._with_dart_diagnostics(
                reason_diagnostics,
                info=latest,
                pages_discovered=pages,
                pages_extracted=pages,
                chunks_created=0,
            )
            status = "empty_library_index" if dropped > 0 else "no_results"
            record = self._record_from_info(latest)
            inspection_action = (
                self._inspection_recovery_action(latest)
                if dropped > 0
                or (record is not None and (record.last_error or "").startswith("partial ingestion:"))
                else None
            )
            next_actions = (
                ["Qualify at least one requested symbol with backticks or a dotted, underscored, or colon-qualified name."]
                if has_unqualified_explicit_query_list
                else [inspection_action] if inspection_action
                else ["Call refresh_library_docs to ingest this library's docs."] if dropped > 0
                else ["Narrow or rephrase the topic, or inspect_library_docs to verify indexed coverage before refreshing."]
            )
            return DocsResult(
                library_id=info.library_id,
                library=latest.library,
                version=latest.version,
                topic=topic,
                refreshed=refreshed,
                stale_before_refresh=stale_before,
                warning=warning,
                last_refreshed_at=latest.last_refreshed_at,
                source_type=info.source_type,
                results=[],
                warnings=warnings,
                requested_version=requested_version,
                resolved_version=latest.resolved_version or latest.version,
                version_source=version_source,
                docs_snapshot_exact=docs_snapshot_exact,
                docs_exactness=docs_exactness,
                docs_binding_source=docs_binding_source,
                confidence=confidence,
                status=status,
                decision="stop",
                reason_code=reason_code,
                request=self._docs_request(input_args, info),
                identity=self._docs_identity(info, docs_url_source=docs_url_source),
                policy=self._docs_policy("error", has_registered_source=True),
                diagnostics=reason_diagnostics,
                next_actions=next_actions,
            )
        chunks, quality_diagnostics = _postprocess_library_chunks(chunks, query)
        chunks, excerpt_diagnostics = _bounded_library_evidence_chunks(
            chunks,
            requirements=requirements,
            max_tokens=tokens or DEFAULT_DOC_TOKENS,
        )
        quality_diagnostics.update(excerpt_diagnostics)
        if not chunks:
            return self._empty_library_index_result(
                info=info,
                latest=latest,
                topic=topic,
                refreshed=refreshed,
                stale_before=stale_before,
                warning=warning,
                warnings=warnings,
                requested_version=requested_version,
                version_source=version_source,
                docs_snapshot_exact=docs_snapshot_exact,
                docs_exactness=docs_exactness,
                docs_binding_source=docs_binding_source,
                confidence=confidence,
                input_args=input_args,
                docs_url_source=docs_url_source,
                diagnostics={
                    **resolution.diagnostics,
                    **quality_diagnostics,
                    "retrieval": retrieval_diagnostics,
                },
                diagnostic_warnings=[
                    *diagnostic_warnings,
                    {"code": "no_qualifying_bounded_passage", "blocking": True},
                ],
            )
        latest_stale = self._is_stale(latest.last_refreshed_at)
        freshness = _freshness_diagnostics(latest.last_refreshed_at, self.stale_after_days, latest_stale)

        # Build exact-version diagnostics if applicable
        final_diagnostics = {**resolution.diagnostics, **quality_diagnostics, "retrieval": retrieval_diagnostics, "freshness": freshness, "warnings": diagnostic_warnings}
        resolved_version = latest.resolved_version or latest.version
        exact_version_match = docs_snapshot_is_exact(requested_version, latest.docs_url_resolved or latest.docs_url) and resolved_version == requested_version if requested_version else None
        if exact_version_resolution and requested_version:
            final_diagnostics["exact_version"] = {
                "expected": requested_version,
                "used": resolved_version,
                "match": exact_version_match,
                "status": "exact_version_indexed" if exact_version_match else "exact_version_fallback_latest",
                "fallback": not exact_version_match,
                "reason_code": None if exact_version_match else "version_mismatch",
            }

        final_diagnostics = self._with_dart_diagnostics(
            final_diagnostics,
            info=latest,
            pages_discovered=pages,
            pages_extracted=pages,
            chunks_created=len(chunks),
        )

        result_chunks = [
            DocsChunk(
                title=(chunk.metadata or {}).get("title"),
                content=chunk.text,
                source=chunk.source,
                url=chunk.source if chunk.source.startswith(("http://", "https://")) else None,
                metadata={**(chunk.metadata or {}), "stale": latest_stale},
            )
            for chunk in chunks
        ]
        snippet_chunks = [
            {
                "title": chunk.title,
                "content": chunk.content,
                "source": chunk.source,
                "url": chunk.url,
                "metadata": {
                    **(chunk.metadata or {}),
                    "source_class": "library_doc",
                    "doc_scope": "library",
                    "origin_lane": "library",
                    "canonical_id": info.library_id,
                    "library_id": info.library_id,
                    "version": resolved_version,
                    "requested_version": requested_version,
                    "docs_exactness": docs_exactness,
                    "docs_binding_source": docs_binding_source,
                    "exact_version_match": exact_version_match,
                },
            }
            for chunk in result_chunks
        ]
        selection_candidates = []
        chunks_by_stable_id = {}
        for index, (chunk, item) in enumerate(zip(result_chunks, snippet_chunks, strict=True)):
            metadata = item["metadata"]
            stable_id = str(
                metadata.get("stable_chunk_id")
                or metadata.get("section_id")
                or metadata.get("chunk_id")
                or "library-" + hashlib.sha256(
                    f"{chunk.source}\0{chunk.title}\0{chunk.content}".encode("utf-8")
                ).hexdigest()[:16]
            )
            candidate = {
                **item,
                "stable_chunk_id": stable_id,
                "parent_logical_id": str(
                    metadata.get("parent_logical_id")
                    or metadata.get("source_id")
                    or chunk.source
                ),
                "display_content_hash": hashlib.sha256(chunk.content.encode("utf-8")).hexdigest(),
                "authority": metadata.get("authority") or "official",
                "docs_exactness": metadata.get("docs_exactness") or docs_exactness,
                "resolved_version": metadata.get("version") or resolved_version,
                "version": metadata.get("version") or resolved_version,
                "docs_snapshot_exact": docs_snapshot_exact,
                "retrieval_rank": index + 1,
            }
            chunk.metadata["stable_chunk_id"] = stable_id
            selection_candidates.append(candidate)
            chunks_by_stable_id[stable_id] = chunk
        selection_decision = select_evidence(
            selection_candidates,
            question=query,
            config=library_docs_selection_config(tokens or DEFAULT_DOC_TOKENS),
            requirements=requirements,
        )
        support_decision = selection_decision.support_decision
        witness_diagnostics = self._bounded_library_index_witness(
            record=record,
            info=info,
            requirements=requirements,
            support_decision=support_decision,
            retrieval_filters=retrieval_filters,
            allowed_ids=allowed_ids,
            expected_roots=expected_roots,
            dispatcher_candidate_ids={item["stable_chunk_id"] for item in selection_candidates},
            resolved_version=resolved_version,
            requested_version=requested_version,
            docs_exactness=docs_exactness,
            docs_snapshot_exact=docs_snapshot_exact,
            exact_version_match=exact_version_match,
        )
        retrieval_diagnostics["index_witness"] = witness_diagnostics
        if witness_diagnostics.get("status") == "witness_found":
            support_decision = support_decision.with_insufficient_reason_code("retrieval_miss")
            selection_decision = replace(
                selection_decision,
                support_decision=support_decision,
            )
        selected_stable_ids = set(support_decision.selected_evidence_ids)
        selected_snippet_chunks = [
            item for item in selection_candidates
            if item["stable_chunk_id"] in selected_stable_ids
        ]
        snippet_presentation = build_snippet_presentation(
            selected_snippet_chunks,
            question=topic or library,
            response_style=response_style,
            lane_priority=["library"],
            support_decision=support_decision,
            requirements=requirements,
        )
        return DocsResult(
            library_id=info.library_id,
            library=latest.library,
            version=latest.version,
            topic=topic,
            refreshed=refreshed,
            stale_before_refresh=stale_before,
            warning=warning,
            last_refreshed_at=latest.last_refreshed_at,
            source_type=info.source_type,
            results=result_chunks,
            warnings=[*warnings, *[warning["code"] for warning in snippet_presentation.warnings]],
            requested_version=requested_version,
            resolved_version=resolved_version,
            version_source=version_source,
            docs_snapshot_exact=docs_snapshot_exact,
            docs_exactness=docs_exactness,
            docs_binding_source=docs_binding_source,
            confidence=confidence,
            status="success",
            request=self._docs_request(input_args, info),
            identity=self._docs_identity(info, docs_url_source=docs_url_source),
            policy=self._docs_policy("success", has_registered_source=True),
            diagnostics=final_diagnostics,
            response_style=snippet_presentation.response_style,
            primary_snippet=snippet_presentation.primary_snippet,
            supporting_snippets=snippet_presentation.supporting_snippets,
            primary_snippets=snippet_presentation.primary_snippets,
            primary_snippet_confidence=snippet_presentation.primary_snippet_confidence,
            primary_snippet_selection_reason=snippet_presentation.primary_snippet_selection_reason,
            primary_snippet_alternatives=snippet_presentation.primary_snippet_alternatives,
            snippet_metrics=snippet_presentation.metrics,
            requirements=requirements,
            selection_decision=selection_decision,
            support_decision=support_decision,
            context_available=bool(result_chunks),
            answer_supported=support_decision.answer_supported,
            answer_available=support_decision.answer_supported,
            support_status=support_decision.support_status,
            reason_code=support_decision.reason_code,
            decision=(
                "answer_returned"
                if support_decision.answer_supported
                else "insufficient_evidence"
            ),
            missing_requirement_ids=list(support_decision.missing_requirement_ids),
            satisfied_requirement_ids=list(support_decision.satisfied_requirement_ids),
            mandatory_requirement_ids=list(support_decision.mandatory_requirement_ids),
            mandatory_coverage=support_decision.mandatory_coverage,
            selected_evidence_ids=list(support_decision.selected_evidence_ids),
            decision_hash=support_decision.decision_hash,
        )
