# Developer's letter

*2026-08-26. An introduction to how this project separates research from
production, and why. Edited in place as the underlying architecture evolves;
see `docs/engine-milestones.md` for the specific, dated evidence behind each
claim here.*

We are building an app, but one of the most important decisions we made is
to keep the research process separate from the production application.

The research side is deliberately isolated. Research code does not go into
production, and it does not write to the database. It only produces simple
Markdown reports under the hypothesis/research-lab area.

The process is very basic on purpose: define a hypothesis, preregister it,
run an isolated experiment, and record the result honestly.

The application itself has a different responsibility.

At the first level, we have the regime module. It exposes one clean output
to the rest of the system, but internally it can contain many small factors
with their own weights and parameters. Those weights may eventually be
informed by things like IC ranking, decay, confidence, or other evidence.

Each factor carries its own status (draft, active, watching, or retired)
and, once decay and confidence measurement exist, its own diagnostics —
weak, decaying, or strong — without changing the external contract of the
regime module.

For example, the existing macro composite may eventually need retiring or
reweighting — not because it was ever named after one person, but because
its indicators were never chair-specific to begin with. We call this module
"macro," not "Powell": its factors (CPI, core PCE, PPI, growth, employment,
and a handful of financial-conditions and rate measures) reflect the Fed's
own institutional framework — inherited from Bernanke's 2012 formal
inflation-targeting regime and continued largely unchanged through Yellen
and Powell — not one chair's personal reaction function. Warsh's own stated
critique is that these standard indicators are backward-looking, lagging
real-time market conditions; that's exactly why we're testing a separate,
forward-looking hypothesis about *his* reaction function independently,
rather than retrofitting it into the existing composite. We have already
preregistered that Warsh hypothesis, with an H-framework and an R0-R6
observation ladder, but none of that has entered production. It stays in
research until there is enough evidence.

The same idea applies to cross-sectional selection. The module has one
standardized output, but internally it can contain multiple factors. Those
factors should represent genuinely different bets, not the same exposure
wearing different names. Eventually they can be combined using a reasonable
weighting scheme, perhaps something as simple as IC-based weighting at
first.

Single-name timing works the same way. The outside world sees a
standardized timing output, while internally different timing factors can
be independently tested, weighted, decayed, replaced, or retired.

Fundamentals are currently a placeholder. We eventually need real isolated
factors such as EPS growth, earnings surprise, guidance revisions, or other
fundamental signals, but those belong to their own experimental family.

Instrument selection is currently more of a proof-of-concept and
feasibility layer.

Portfolio-level risk controls — covariance, concentration limits,
cross-strategy correlation-aware sizing — are still placeholder. The
existing exposure envelope (a regime-confidence-scaled gross exposure
multiplier and sleeve targets) is real and runs every pipeline call, just
naive and not yet validated.

The research philosophy behind all of this is controlled experimentation.

Each factor is treated as a single effective ingredient. We test it
independently before combining it with anything else.

The final production system, however, is a kind of polytherapy.

Before tuning the polytherapy, we first need to know whether each
individual ingredient actually works, what its direction is, how strong it
is, and how quickly it decays.

There is also an important software-engineering constraint.

The entire application must remain runnable end to end.

If every research factor happens to fail, the software cannot suddenly
become a page full of "not available" states. That would make the staging
application look broken even though the research process is actually
behaving correctly.

Instead, every factor should honestly carry its own status. A factor may be
rejected, retired, weak, placeholder, or unvalidated, but the application
should still be able to complete the full pipeline.

A pipeline completing successfully does not mean the system is tradable.

Those are two completely different standards.

Trading readiness is a much later problem. We may not even begin serious
paper-trading validation for several months.

Right now the application has a staging-mode toggle. The goal is
reproducibility: anyone should be able to clone the repository, configure
the environment, go to `http://127.0.0.1:8000/operations`, click "Run
available stages," and run the same deterministic pipeline. The
*methodology* is deterministic and reproducible — same code, same real
data source, same computation. The *output* is not: `fetch_data` pulls
live FRED and Yahoo data every run, so two people running it on different
days will see different real numbers, because the market moved. That's
expected, not a bug — this is not a canned demo standing in as a pipeline;
a separate, explicitly synthetic seed exists for when identical numbers
every time are actually what's wanted.

Because of that, all intentionally selected symbols, placeholder
strategies, and staging methods must be database-driven.

The application must not quietly choose its own default symbols, silently
retune parameters, or automatically retire a factor just because research
later says the factor is bad.

If we remove a production factor too early, the pipeline may stop working.
That would mix research truth with software availability.

This repository is therefore shared by two very different roles.

The product-engineering side cares about whether the application works,
whether the contracts are stable, whether the pipeline finishes, and
whether the UI remains coherent.

The research side cares about whether a factor is actually valid.
Researchers should be free to mark something as rejected, weak, decaying,
or useless without worrying about whether doing so breaks the staging
application.

Research experiments live in the isolated research area. They run
disposable code and write simple experiment reports into `docs/hypotheses`;
the code lives in `backend/research_lab`.

That means we can register and test many hypotheses without constantly
changing staging-mode code.

The staging application can continue running on deliberately simple or even
outdated placeholder logic — basic macro inputs, old MACD timing logic,
simple momentum ranking — without pretending those methods have research
support.

Only after we reach agreement on a factor, the experiment is reproducible,
and regression tests pass, should a successful factor graduate into
production.

At that point it enters the appropriate ensemble: macro, cross-sectional
selection, timing, fundamentals, risk, or another family.

Then, if necessary, an older production factor can genuinely be retired and
replaced.

The important point is that the external module contract stays stable, so
the application still runs.

The experimental area itself can operate at different levels of
granularity.

Some experiments only ask whether a factor has any evidence at all and
whether it represents a genuinely different bet from existing factors.

At a higher level, we can start testing portfolio return, drawdown, decay,
turnover, parameter stability, and implementation costs.

Much later, parameter optimization could become more sophisticated. Genetic
algorithms, neural networks, or other optimization methods are all
possible.

But those methods only make sense after we know what we are optimizing.

At the highest level, the Today/Workspace interface should eventually look
seamless and professional. A desk user should see a clean, stable summary.

Behind that interface, however, researchers may have run hundreds of
experiments and retired most of them.

That separation is intentional.

The research lab is the isolated experimental backend.

Operations is administrative work.

Workspace is what the desk user cares about.

The desk user does not need to know how an administrator ran the pipeline,
and the administrator does not need to know how many research experiments
happened before a new strategy was gradually promoted into Staging Production.

We have finally reached the point where all six real compute stages run
end to end (the final publish step stays scaffolded, by design, not
oversight), which means we can now start doing real preregistered research
instead of continuously rebuilding infrastructure.

From now on, we want to keep experimental boundaries clean.

If we are testing a price/volume factor, we should not suddenly inject EPS
data into the experiment.

If we are testing cross-sectional momentum, we should not change the
result because we believe the company is fundamentally overvalued or
sentiment is overheated.

Sentiment and fundamentals may matter, but they are different hypotheses
and deserve their own isolated experiments.

Only later do we combine independently supported factors.

That is where ideas such as the Fundamental Law become relevant: breadth
matters, but only when the bets are genuinely independent. Adding twenty
versions of the same exposure does not create twenty independent signals.
(Grinold, R. C. (1989). The fundamental law of active management. *The
Journal of Portfolio Management*, 15(3), 30–37; expanded in Grinold, R. C.,
& Kahn, R. N. (1999). *Active Portfolio Management: A Quantitative Approach
for Providing Superior Returns and Controlling Risk* (2nd ed.). McGraw-Hill.
The formula — Information Ratio ≈ Information Coefficient × √Breadth — is
exactly why this project's own effective-number-of-bets check exists:
breadth in that formula means independent bets, not raw factor count.)

We also do not want to perform meaningless mathematical transformations
just because they improve a backtest.

We are not interested in taking a factor, applying square roots, powers,
integrals, or hundreds of transformations until something becomes
significant.

That is just another route to overfitting.

However, this does not mean mathematical transformations are forbidden.

A transformation is reasonable when there is an actual hypothesis behind
it.

For example, if we are studying medium-term price momentum or mean
reversion, using a `12-month minus 1-month` construction is not an
arbitrary mathematical trick. There is a reason for excluding the most
recent month: the first month may contain short-term reversal, crowding,
liquidity effects, or a different behavioral regime that contaminates the
medium-term signal.

So the rule is not "do not play mathematical games."

Mathematical experimentation is fine. Modern machine learning does plenty
of it.

The requirement is that we should be able to explain why a transformation
might represent a real mechanism before we start optimizing around it.

That is roughly where the project stands today.

The application infrastructure is finally stable enough that research can
become the main activity rather than infrastructure work. From here, the
goal is simple: isolate one hypothesis at a time, test it honestly, keep
failed results, promote only what survives, and let the production system
evolve slowly without breaking the staging application.

— Developer
